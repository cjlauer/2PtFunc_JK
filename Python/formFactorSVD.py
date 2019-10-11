from sys import stderr
import time
import numpy as np
import argparse as argp
from scipy.optimize import curve_fit
import functions as fncs
import mpi_functions as mpi_fncs
import readWrite as rw
import physQuants as pq
import lqcdjk_fitting as fit
from mpi4py import MPI

particle_list = fncs.particleList()
format_list = fncs.dataFormatList()
form_factor_list = fncs.formFactorList()

#########################
# Parse input arguments #
#########################

parser = argp.ArgumentParser( description="Calculate form factors using SVD" )

parser.add_argument( "threep_dir", action='store', type=str )

parser.add_argument( "threep_tokens", action='store', \
                     type=lambda s: [str(token) for token in s.split(',')], \
                     help="Comma seperated list of filename tokens. " \
                     + "CPU: part before tsink, part before momentum " \
                     + "boost components. GPU: part before momentum " \
                     + "boost components, part after momentum boost; " \
                     + "* for configuration number." )

parser.add_argument( "twop_dir", action='store', type=str )

parser.add_argument( "twop_template", action='store', type=str )

parser.add_argument( "mEff_fit_range_end", action='store', type=int )

parser.add_argument( "particle", action='store', \
                     help="Particle to calculate form factor for. " \
                     + "Should be 'pion', 'kaon', or 'nucleon'.", \
                     type=str )

parser.add_argument( "form_factor", action='store', \
                     help="Form factor to calculate. " \
                     + "Should be 'EM', or '1D'.", \
                     type=str )

parser.add_argument( 't_sink', action='store', \
                     help="Comma seperated list of t sink's", \
                     type=lambda s: [int(item) for item in s.split(',')] )

parser.add_argument( "L", \
                     action='store', type=int )

parser.add_argument( "lattice_spacing", \
                     action='store', type=float )

parser.add_argument( "threep_final_momentum_squared", \
                     action='store', type=int )

parser.add_argument( "binSize", action='store', type=int )

parser.add_argument( "-o", "--output_template", action='store', \
                     type=str, default="./*.dat" )

parser.add_argument( "-tsf", "--two_state_fit", action='store_true', \
                     help="Performs the two-state fit if supplied" )

parser.add_argument( "-f", "--data_format", action='store', \
                     help="Data format. Should be 'gpu', " \
                     + "'cpu', or 'ASCII'.", \
                     type=str, default="gpu" )

parser.add_argument( "-c", "--config_list", action='store', \
                     type=str, default="" )

parser.add_argument( "-m", "--momentum_transfer_list", action='store', \
                     type=str, default="" )

args = parser.parse_args()

#########
# Setup #
#########

# Set MPI values

comm = MPI.COMM_WORLD
procNum = comm.Get_size()
rank = comm.Get_rank()

# Input directories and filename templates

threepDir = args.threep_dir

twopDir = args.twop_dir

threep_tokens = args.threep_tokens

twop_template = args.twop_template

# First and last points to fit ratios

rangeEnd_mEff = args.mEff_fit_range_end

# Info on what to analyze

particle = args.particle

formFactor = args.form_factor

tsink = args.t_sink
tsinkNum = len( tsink )
ts_range_str = "tsink" + str(tsink[0]) + "_" + str(tsink[-1])

# Other info

L = args.L
a = args.lattice_spacing

binSize = args.binSize

output_template = args.output_template

dataFormat = args.data_format

QFile = args.momentum_transfer_list

momSq = args.threep_final_momentum_squared

tsf = args.two_state_fit

# Get configurations from given list or from given 
# threep directory if list not given

configList = np.array( fncs.getConfigList( args.config_list, threepDir ) )
configNum = len( configList )

# Number of configurations on each process

procSize = configNum // procNum

# Total number of bins across processes

binNum_glob = configNum // binSize

# Global index of confs for each process

iconf = np.array( [ np.array( [ r * procSize + cl \
                                for cl in range( procSize ) ], dtype=int )
                    for r in range( procNum ) ] )

# List of configurations on this process

configList_loc = configList[ iconf[ rank ] ]

# Global index of first conf of bins for each process

binStart = np.array( [ np.array( [ cl for cl in iconf[ r ] \
                                   if cl % binSize == 0 ], dtype=int )
                       for r in range( procNum ) ] )

# Global bin index for each process

bin_glob = binStart // binSize

# Number of bins for each process

binNum = [ len( binStart[ r ] ) for r in range( procNum ) ]

# Number of bins for this process

binNum_loc = binNum[ rank ]

recvCount, recvOffset = mpi_fncs.recvCountOffset( procNum, binNum )

# Check inputs

assert particle in particle_list, \
    "Error: Particle not supported. " \
    + "Supported particles: " + str( particle_list )

assert dataFormat in format_list, \
    "Error: Data format not supported. " \
    + "Supported particles: " + str( format_list )

assert formFactor in form_factor_list, \
    "Error: Form factor not supported. " \
    + "Supported form factors: " + str( form_factor_list )

assert configNum % binSize == 0, "Number of configurations " \
    + str( configNum ) + " not evenly divided by bin size " \
    + str( binSize ) + "."

assert configNum % procNum == 0, "Number of configurations " \
    + str( configNum ) + " not evenly divided by number of processes " \
    + str( procNum ) + "."

if particle == "pion":

    projector = [ "" ]

    flavNum = 1
    flav_str = [ "up" ]

    if formFactor == "1D":

        ratioNum = 7

    else:

        mpi_fncs.mpiPrintErr( "Error: Form factor no supported for " \
                              + particle, comm )

elif particle == "kaon":

    projector = [ "" ]

    flavNum = 2
    flav_str = [ "up", "strange" ]

    ratioNum = 10

    if formFactor == "1D":

        ratioNum = 7

    else:

        mpi_fncs.mpiPrintErr( "Error: Form factor no supported for " \
                              + particle, comm )

elif particle == "nucleon":

    projector = [ "0", "4", "5", "6" ]

    flavNum = 2
    flav_str = [ "IV", "IS" ]

    if formFactor == "EM":

        ratioNum = 10

    else:

        mpi_fncs.mpiPrintErr( "Error: Form factor no supported for " \
                              + particle, comm )

projNum = len( projector )

if formFactor == "EM":

    Z = 1.0

elif formFactor == "1D":

    Z = 1.123

# Read final momentum list

finalMomList = []

if dataFormat == "cpu":

    finalMomList = np.array ( rw.getDatasets( twopDir, \
                                              [ configList_loc[0] ], \
                                              twop_template, \
                                              "twop_".format( particle ), \
                                              "ave16", \
                                              "msq{:0>4}".format( momSq ), \
                                              "mvec" )[ 0, 0, 0, ... ], \
                              dtype = int )

else:

    if momSq == 0:

        finalMomList = np.array( [ [ 0, 0, 0 ] ] )

    else:

        mpi_fncs.mpiPrintErr( "ERROR: nonzero momenta boost not yet " \
               + "supported for gpu or ASCII format", comm )
        
#mpi_fncs.mpiPrint(finalMomList.shape,rank)

# Multiply finalMomList by -1 because three-point functions are named
# opposite their sign (sign of phase negative because adjoint taken of
# sequential propagator)

finalMomList = -1 * finalMomList

finalMomNum = len( finalMomList )

# Momentum list
"""
Q_threep_template = "{0}{1}{2}".format( threep_tokens[0], \
                                        tsink[0], \
                                        threep_tokens[1] ) \
    + "{0:+d}_{1:+d}_{2:+d}.{3}.h5".format( finalMomList[0,0],\
                                            finalMomList[0,1],\
                                            finalMomList[0,2],\
                                            flav_str[0] )
"""
#mpi_fncs.mpiPrint(Q_threep_template,rank)

Q, Qsq, Qsq_start, \
    Qsq_end = rw.readAndProcessQList( QFile, \
                                      twopDir, configList, \
                                      twop_template, \
                                      dataFormat )

QNum = len( Q )

QsqNum = len( Qsq )

############################
# Read Two-point Functions #
############################

# Zero momentum two-point functions
# twop[ c, q, t ]

t0 = time.time()

twop_loc = rw.readTwopFile_Q( twopDir, configList_loc, twop_template, \
                              Q, Qsq, Qsq_start, Qsq_end, \
                              particle, dataFormat )

twop_loc = np.asarray( twop_loc, order='c' )

mpi_fncs.mpiPrint( "Read two-point functions from files " \
                   + "in {:.3} seconds".format( time.time() - t0 ), rank )

T = twop_loc.shape[ -1 ]

# Gather two-point functions

twop = np.zeros( ( configNum, QNum, T ), dtype=float )

comm.Allgather( twop_loc, twop )

#################################
# Jackknife two-point functions #
#################################

# Time dimension length after fold

T_fold = T // 2 + 1

if binNum_loc:

    twop_jk_loc = np.zeros( ( binNum_loc, QNum, T ) )

    for q in range( QNum ):

        twop_jk_loc[:,q,:] = fncs.jackknifeBinSubset( twop[:,q,:], \
                                                      binSize, \
                                                      bin_glob[ rank ] )

    if particle == "nucleon":

        mEff_loc = pq.mEff( twop_jk_loc[:,0,:] )

    else:

        # twop_fold[ b, t ]

        twop_fold = fncs.fold( twop_jk_loc[ :, 0, : ] )

        # mEff[ b, t ]

        mEff_loc = pq.mEffFromSymTwop( twop_fold )

else:

    twop_jk_loc = np.array( [] )

    mEff_loc = np.array( [] )

##################
# Effective mass #
##################

if rank == 0:

    twop_jk = np.zeros( ( binNum_glob, QNum, T ) )


    if particle == "nucleon":

        mEff = np.zeros( ( binNum_glob, T ) )

    else:

        mEff = np.zeros( ( binNum_glob, T_fold ) )

else:

    twop_jk = None
    mEff = None

recvCount, recvOffset = mpi_fncs.recvCountOffset( procNum, binNum )

if particle == "nucleon":

    comm.Gatherv( mEff_loc, [ mEff, recvCount * T, \
                              recvOffset * T, MPI.DOUBLE ], \
                  root=0 )

else:

    comm.Gatherv( mEff_loc, [ mEff, recvCount * T_fold, \
                              recvOffset * T_fold, MPI.DOUBLE ], \
                  root=0 )

comm.Gatherv( twop_jk_loc, [ twop_jk, recvCount * QNum * T, \
                             recvOffset * QNum * T, \
                             MPI.DOUBLE ], \
              root=0 )

if rank == 0:

    # mEff_avg[ t ]

    mEff_avg = np.average( mEff, axis=0 )
    mEff_err = fncs.calcError( mEff, binNum_glob )

    avgOutputFilename = output_template.replace( "*", "mEff_avg" )
    rw.writeAvgDataFile( avgOutputFilename, mEff_avg, mEff_err )

    # Fit the effective mass and two-point functions 

    mEff_fit = np.zeros( binNum_glob )

    if particle == "nucleon":

        # Loop over bins
        for b in range( binNum_glob ):
            
            # Perform the plateau fit

            rangeStart_mEff = 13

            mEff_fit[ b ] = fit.fitPlateau( mEff, mEff_err, \
                                            rangeStart_mEff, \
                                            rangeEnd_mEff )

        # End loop over bins

    else:

        try:

            fitResults = fit.mEffTwopFit( mEff, twop_fold, \
                                          rangeEnd_mEff, 0, L, tsf, \
                                          mEff_t_low_range=[12], \
                                          twop_t_low_range=[3], \
                                          checkFit=False )
            
        except fit.lqcdjk_BadFitError as error:
        
            mpi_fncs.mpiPrintErr( "ERROR (lqcdjk_fitting.mEffTwopFit):" \
                                  + str( error ), comm )
            
        fitParams = fitResults[ 0 ]
        chiSq = fitResults[ 1 ]
        mEff_fit = fitResults[ 2 ]
        rangeStart = fitResults[ 3 ]
        rangeStart_mEff = fitResults[ 4 ]

        curve = np.zeros( ( binNum_glob, 50 ) )

        t_s = np.concatenate( ( np.linspace( rangeStart, \
                                             rangeEnd_mEff, 25 ), \
                                np.linspace( T - rangeEnd_mEff, \
                                             T- rangeStart, 25 ) ) )
            
        twopFit_str = "2s" + str( rangeStart ) \
                      + ".2e" + str( rangeEnd_mEff )
        
        if tsf:

            c0 = fitParams[ :, 0 ]
            c1 = fitParams[ :, 1 ]
            E0 = fitParams[ :, 2 ]
            E1 = fitParams[ :, 3 ]

            # Calculate fitted curve

            for b in range( binNum_glob ):
                for t in range( t_s.shape[ -1 ] ):
                
                    curve[ b, t ] = fit.twoStateTwop( t_s[ t ], T, \
                                                      c0[ b ], c1[ b ], \
                                                      E0[ b ], E1[ b ] )
                        
                # End loop over tsink
            # End loop over bins

            curveOutputFilename \
                = output_template.replace( "*", \
                                           "twop_twoStateFit_curve_" \
                                           + twopFit_str )
            chiSqOutputFilename \
                = output_template.replace( "*", \
                                           "twop_twoStateFit_chiSq_" \
                                           + twopFit_str )

        else: # One-state fit

            G = fitParams[ :, 0 ]
            E = fitParams[ :, 1 ]

            # Calculate fitted curve

            for b in range( binNum_glob ):
                for t in range( t_s.shape[ -1 ] ):
                
                    curve[ b, t ] = fit.oneStateTwop( t_s[ t ], T, \
                                                      G[ b ], E[ b ] )
                        
                # End loop over tsink
            # End loop over bins

            curveOutputFilename \
                = output_template.replace( "*", \
                                           "twop_oneStateFit_curve_" \
                                           + twopFit_str )
            chiSqOutputFilename \
                = output_template.replace( "*", \
                                           "twop_oneStateFit_chiSq_" \
                                           + twopFit_str )

        # End if not two-state fit

        curve_avg = np.average( curve, axis=0 )
        curve_err = fncs.calcError( curve, binNum_glob )
            
        chiSq_avg = np.average( chiSq, axis=0 )
        chiSq_err = fncs.calcError( chiSq, binNum_glob )
            
        # Write output files

        rw.writeAvgDataFile_wX( curveOutputFilename, t_s, \
                                curve_avg, curve_err )
        
        rw.writeFitDataFile( chiSqOutputFilename, chiSq_avg, \
                             chiSq_err, rangeStart, rangeEnd_mEff )

    # End if meson

    # mEff_fit_avg
        
    mEff_fit_avg = np.average( mEff_fit, axis=0 )
    mEff_fit_err = fncs.calcError( mEff_fit, binNum_glob )
        
    Qsq_GeV = pq.convertQsqToGeV( Qsq, a * mEff_fit_avg, a, L )

    mEff_range_str = "2s" + str( rangeStart_mEff ) \
                     + ".2e" + str( rangeEnd_mEff )

    mEff_outputFilename = output_template.replace( "*", "mEff_fit_" \
                                                   + mEff_range_str )
    rw.writeFitDataFile( mEff_outputFilename, mEff_fit_avg, \
                         mEff_fit_err, rangeStart_mEff, rangeEnd_mEff )

# End if first process

"""
if momSq > 0:

    twop_boost = np.zeros( ( finalMomNum, configNum, T ) )

    comm.Allgather( twop_boost_loc, twop_boost )

else:
    
    twop_boost = np.array( [] )

if rank == 0:
        
    twop_boost_jk = np.zeros( ( finalMomNum, binNum_glob, T ) )

else:

    twop_boost_jk = np.array( [ None for imom in range( finalMomNum ) ] )
    #avgX = np.array( [ [ [ None for ts in tsink ] \
    #                     for f in flav_str ] \
    #                   for imom in range( finalMomNum ) ] )
"""
if momSq > 0:
        
    # Loop over final momenta
    for imom in range( finalMomNum ):

        #########################################
        # Jackknife boosted two-point functions #
        #########################################

        if binNum_loc:

            twop_boost_jk = fncs.jackknifeBinSubset( twop_boost[ imom ], \
                                                         binSize, \
                                                         bin_glob[ rank ] )

        else:

            twop_boost_jk = np.array( [] )
        """
        comm.Gatherv( twop_boost_jk, [ twop_boost_jk[ imom ], \
                                           recvCount * T, recvOffset * T, \
                                           MPI.DOUBLE ], root=0 )
        """
    # End loop over final momenta

else:

    twop_boost_jk = np.array( [ twop_jk_loc ] )

##############################
# Read three-point functions #
##############################

"""
# threep_jk[ ts ][ p, flav, b, Q, ratio, t ]

if rank == 0:

    threep_jk = fncs.initEmptyList( tsinkNum, 1 )

else:

    threep_jk = np.array( [ [ None for ts in tsink ]
                            for imom in range( finalMomNum ) ] )
"""
# Loop over tsink
for ts, its in zip( tsink, range( tsinkNum ) ) :

    if particle == "nucleon":

        threepTimeNum = ts + 1

    else:

        threepTimeNum = T

    # Loop over final momenta
    for ip in range( finalMomNum ):

        t0_ts = time.time()

        # threep_loc[ flav, conf, Q, ratio, t ]

        threep_loc = rw.readFormFactorThreep( threepDir, configList_loc, \
                                              threep_tokens, Qsq, \
                                              Qsq_start, Qsq_end, \
                                              QNum, ts, projector, \
                                              finalMomList[ ip ], \
                                              particle, dataFormat, \
                                              formFactor )

        mpi_fncs.mpiPrint( "Read three-point functions from files " \
                           + "for tsink {} in {:.4}".format( ts, \
                                                             time.time() \
                                                             - t0_ts ) \
                           + " seconds.", rank )

        # Loop over flavor
        for iflav in range( flavNum ):

            # threep[ c, Q, r, t ]

            threep = np.zeros( ( configNum, QNum, \
                                 ratioNum, threepTimeNum ) )

            comm.Allgather( threep_loc[ iflav ], \
                            threep )

            # If bin on this process
            if binNum_loc:

                ratio_loc = np.zeros( ( binNum_loc, QNum, \
                                        ratioNum, threepTimeNum ) )

                # Loop over ratio
                for ir in range( ratioNum ):

                    # Jackknife
                    # threep_jk[ b, Q, t ]

                    threep_jk = np.zeros( ( binNum_loc, QNum, \
                                            threepTimeNum ) )

                    # Loop over Q
                    for iq in range( QNum ):

                        threep_jk[:, \
                                  iq, \
                                  :]=fncs.jackknifeBinSubset(threep[:, iq, \
                                                                    ir, \
                                                                    : ], \
                                                             binSize, \
                                                             bin_glob[rank])

                    # End loop over Q

                    #mpi_fncs.mpiPrint(threep_jk,rank)

                    ####################
                    # Calculate ratios #
                    ####################

                    ratio_loc[...,ir,:] = pq.calcRatio_Q( threep_jk, \
                                                          twop_boost_jk[ ip ], \
                                                          ts )

                # End loop over ratio
            # End if bin on process
            else:

                ratio_loc = np.array( [] )
        
            ratio = np.zeros( ( binNum_glob, QNum, \
                                ratioNum, threepTimeNum ) )

            comm.Allgatherv( ratio_loc, \
                             [ ratio, \
                               recvCount * QNum \
                               * ratioNum * threepTimeNum, \
                               recvOffset * QNum \
                               * ratioNum * threepTimeNum, \
                               MPI.DOUBLE ] )

            ratio_avg = np.average( ratio, axis=0 )
            ratio_err = fncs.calcError( ratio, binNum_glob )

            """
            ff_outFilename = output_template.replace( "*", \
                                                      particle + "_" \
                                                      + flav_str[iflav] \
                                                      + "_formFactor_" \
                                                      + "tsink" \
                                                      + str(ts) )

            
            
            rw.writeAvgFormFactorFile( ff_outFilename, Q, \
                                       ratio_avg[:,0,:], ratio_err[:,0,:] )
            """    
            #mpi_fncs.mpiPrintAllRanks(ratio_err,comm)

            if binNum_loc:

                # ratio_fit[ b, Q, ratio ]
             
                ratio_fit_loc=fit.fitGenFormFactor(ratio_loc, \
                                                   ratio_err, \
                                                   ts // 2 - 2, \
                                                   ts // 2 + 2)

            else: 

                ratio_fit_loc = np.array( [] )

            if rank == 0:

                ratio_fit = np.zeros( ( binNum_glob, QNum, ratioNum ) )

            else:

                ratio_fit = None

            comm.Gatherv( ratio_fit_loc, \
                          [ ratio_fit, \
                            recvCount * QNum * ratioNum, \
                            recvOffset * QNum * ratioNum, \
                            MPI.DOUBLE ], root=0 )

            if rank == 0:

                # ratio_fit_err[ Q, ratio ]

                ratio_fit_err = fncs.calcError( ratio_fit, binNum_glob )        
            
                ###############################
                # Calculate kinematic factors #
                ###############################

                # kineFacter[ b, Q, r, [ GE, GM ] ]
                
                #print("ratio_fit_err:")
                #print(ratio_fit_err)
                #print("mEff_fit")                
                #print(mEff_fit[0])

                kineFactor = pq.formFactorKinematic( ratio_fit_err, \
                                                     mEff_fit, Q, L, \
                                                     particle, formFactor )

                #print(kineFactor[0])

                # For EM form factor:
                # A = GE, B = GM
                # For generalized 1D form factor:
                # A = A20, B = A22

                A = np.zeros( ( QsqNum, binNum_glob ) )
                B = np.zeros( ( QsqNum, binNum_glob ) )

                for qsq in range( QsqNum ):

                    ###############
                    # Perform SVD #
                    ###############

                    kineFactor_Qsq \
                        = kineFactor[ :, \
                                      Qsq_start[ qsq ]:Qsq_end[ qsq ] + 1, \
                                      ... ].reshape( binNum_glob, \
                                                     ( Qsq_start[ qsq ] \
                                                       - Qsq_end[ qsq ] \
                                                       + 1 ) \
                                                     * ratioNum, 2 )

                    u, s, vT = np.linalg.svd( kineFactor_Qsq, \
                                              full_matrices=False )

                    #print("U")
                    #print(u[0])
                    #print("S")
                    #print(s[0])
                    #print("V^T")
                    #print(vT[0])

                    ##############################
                    # Calculate ( v s^-1 u^T )^T #
                    ##############################

                    uT = np.transpose( u, ( 0, 2, 1 ) )
                    v = np.transpose( vT, ( 0, 2, 1 ) )

                    #print("U^T")
                    #print(uT[0])
                    #print("V")
                    #print(v[0])

                    smat = np.zeros( ( u.shape[-1], vT.shape[-2] ) )
                    smat_inv = np.zeros( ( binNum_glob, ) \
                                         + np.transpose( smat ).shape )

                    for b in range( binNum_glob ):

                        smat[ :vT.shape[ -2 ], \
                              :vT.shape[ -2 ] ] = np.diag( s[ b ] )

                        smat_inv[ b ] = np.linalg.pinv( smat )

                    # End loop over bins

                    # decomp = ( u s v^T )^-1
                    # decomp[ b, Q, ratio, [ A, B ] ]

                    decomp= np.transpose( v @ smat_inv @ uT, \
                                          (0,2,1) ).reshape( binNum_glob,\
                                                             Qsq_end[qsq]\
                                                             -Qsq_start[qsq]\
                                                             + 1, \
                                                             ratioNum, 2 )

                    A[qsq], B[qsq] = pq.decompFormFactors( decomp, \
                                                           ratio_fit, \
                                                           ratio_fit_err, \
                                                           Qsq_start[ qsq ], \
                                                           Qsq_end[ qsq ] )

                # End loop over Q^2

                # Average over bins

                A_avg = np.average( A, axis=-1 )
                A_err = fncs.calcError( A, binNum_glob, axis=-1 )

                B_avg = np.average( B, axis=-1 )
                B_err = fncs.calcError( B, binNum_glob, axis=-1 )

                ################
                # Write output #
                ################

                if formFactor == "EM":

                    ff_str = [ "GE", "GM" ]

                elif formFactor == "1D":

                    ff_str = [ "A20", "A22" ]

                output_filename = output_template.replace( "*", \
                                                           particle + "_" \
                                                           + flav_str[iflav] \
                                                           + "_" + ff_str[ 0 ]\
                                                           + "_tsink" \
                                                           + str( ts ) )
                rw.writeAvgDataFile_wX( output_filename, Qsq_GeV, \
                                           A_avg, A_err )

                output_filename = output_template.replace( "*", \
                                                           particle + "_" \
                                                           + flav_str[iflav] \
                                                           + "_" + ff_str[ 1 ]\
                                                           + "_tsink" \
                                                           + str( ts ) )
                rw.writeAvgDataFile_wX( output_filename, Qsq_GeV, \
                                           B_avg, B_err )

            # End if first process
        # End loop over flavor
    # End loop over p
# End loop over tsink
