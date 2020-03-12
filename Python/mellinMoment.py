import sys
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

np.set_printoptions(threshold=sys.maxsize)

L = 32.0

particle_list = [ "pion", "kaon", "nucleon" ]

format_list = [ "gpu", "cpu" ]

moment_list = [ 1, 2, 3 ]

#########################
# Parse input arguments #
#########################

parser = argp.ArgumentParser( description="Calculate a mellin moment up to "
                              + " the third order" )

parser.add_argument( "threep_dir", action='store', type=str )

parser.add_argument( "threep_tokens", action='store',
                     type=lambda s: [str(token) for token in s.split(',')],
                     help="Comma seperated list of filename tokens. "
                     + "CPU: part before tsink, part before momentum "
                     + "boost components. GPU: part before momentum "
                     + "boost components, part after momentum boost; "
                     + "* for configuration number." )

parser.add_argument( "twop_dir", action='store', type=str )

parser.add_argument( "twop_template", action='store', type=str )

parser.add_argument( "fit_range_end", action='store', type=int )

parser.add_argument( "particle", action='store',
                     help="Particle to calculate gA for. "
                     + "Should be 'pion' or 'kaon'.", type=str )

parser.add_argument( 't_sink', action='store',
                     help="Comma seperated list of t sink's",
                     type=lambda s: [int(item) for item in s.split(',')] )

parser.add_argument( "mom_squared", action='store', type=int )

parser.add_argument( "moment", action='store', type=int )

parser.add_argument( "binSize", action='store', type=int )

parser.add_argument( "-o", "--output_template", action='store',
                     type=str, default="./*.dat" )

parser.add_argument( "-sn", "--source_number", action='store', type=int,
                     help="Number of sources correlators were averaged "
                     + "over", default=16 )

parser.add_argument( "-tsf", "--two_state_fit", action='store_true',
                     help="Performs the two-state fit if supplied" )

parser.add_argument( "--tsf_fit_start", action='store', type=int,
                     help="If given, will perform two-state fit on effective "
                     + "mass starting at given t value, otherwise, will "
                     + "use lowest t value which satisfies condition." )

parser.add_argument( "--twop_fit_start", action='store', type=int,
                     help="If given, will perform one- or two-state fit on "
                     + "two-point functions starting at given t value, "
                     + "otherwise, will use lowest t value which satisfies "
                     + "condition." )

parser.add_argument( "--plat_fit_start", action='store', type=int,
                     help="If given, will perform plateau fit on effective "
                     + "mass starting at given t value, otherwise, will "
                     + "use lowest t value which satisfies condition." )

parser.add_argument( "-f", "--data_format", action='store',
                     help="Data format. Should be 'gpu' or 'cpu'.",
                     type=str, default="gpu" )

parser.add_argument( "-c", "--config_list", action='store',
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

# Last point to fit

rangeEnd = args.fit_range_end

# Info on what to analyze

particle = args.particle

tsink = args.t_sink
tsinkNum = len( tsink )
ts_range_str = "tsink" + str(tsink[0]) + "_" + str(tsink[-1])

# Other info

binSize = args.binSize

output_template = args.output_template

tsf_fitStart = args.tsf_fit_start
twop_fitStart = args.twop_fit_start
plat_fitStart = args.plat_fit_start

if tsf_fitStart and plat_fitStart:

    checkFit = False

else:

    checkFit = True

srcNum = args.source_number

tsf = args.two_state_fit

dataFormat = args.data_format

momSq = args.mom_squared

moment = args.moment

# Get configurations from given list or from given 
# threep directory if list not given

configList = np.array( fncs.getConfigList( args.config_list, threepDir ) )
configNum = len( configList )

# Check inputs

assert particle in particle_list, \
    "Error: Particle not supported. " \
    + "Supported particles: " + str( particle_list )

if particle == "pion":

    flavNum = 1

else:

    flavNum = 2

# Set string for up and strange quark.
# If pion, will not access strange.

flav_str = [ "u", "s" ]

assert dataFormat in format_list, \
    "Error: Data format not supported. " \
    + "Supported particles: " + str( format_list ) \

assert configNum % binSize == 0, "Number of configurations " \
    + str( configNum ) + " not evenly divided by bin size " \
    + str( binSize ) + "."

assert configNum % procNum == 0, "Number of configurations " \
    + str( configNum ) + " not evenly divided by number of processes " \
    + str( procNum ) + "."

assert moment in moment_list, \
    "Error: Moment order not supported. " \
    + "Supported moments: " + str( moment_list )


if moment == 1:

    Z = 1.123
    moment_str = "avgX"

elif moment == 2:

    Z = 1.0
    moment_str = "avgX2"

elif moment == 3:

    Z = 1.0
    moment_str = "avgX3"

# Number of configurations on each process

procSize = configNum // procNum

# Total number of bins across processes

binNum_glob = configNum // binSize

# Global index of confs for each process

iconf = np.array( [ np.array( [ r * procSize + cl
                                for cl in range( procSize ) ], dtype=int )
                    for r in range( procNum ) ] )

# List of configurations on this process

configList_loc = configList[ iconf[ rank ] ]

# Global index of first conf of bins for each process

binStart = np.array( [ np.array( [ cl for cl in iconf[ r ]
                                   if cl % binSize == 0 ], dtype=int )
                       for r in range( procNum ) ] )

# Global bin index for each process

bin_glob = binStart // binSize

# Number of bins for each process

binNum = [ len( binStart[ r ] ) for r in range( procNum ) ]

# Number of bins for this process

binNum_loc = binNum[ rank ]

recvCount, recvOffset = mpi_fncs.recvCountOffset( procNum, binNum )

# Read momentum list

momList = rw.readMomentaList( twopDir, twop_template,
                              configList_loc[ 0 ], particle,
                              srcNum, momSq, dataFormat, comm )

momBoostNum = len( momList )

############################
# Read Two-point Functions #
############################

# Zero momentum two-point functions
# twop[ c, t ]

twop = rw.readTwopFile_zeroQ( twopDir, configList_loc, configNum,
                              twop_template, srcNum, 0, dataFormat,
                              comm )

# Time dimension length

T = twop.shape[ -1 ]

# Time dimension length after fold

T_fold = T // 2 + 1

##########################################
# Jackknife and fold two-point functions #
##########################################

if binNum_loc:

    twop_jk_loc = fncs.jackknifeBinSubset( twop, binSize, bin_glob[ rank ] )

    # twop_fold[ b, t ]

    twop_fold_loc = fncs.fold( twop_jk_loc )

    # mEff[ b, t ]

    mEff_loc = pq.mEffFromSymTwop( twop_fold_loc )

else:

    twop_jk_loc = np.array( [] )

    twop_fold_loc = np.array( [] )

    mEff_loc = np.array( [] )

##################
# Effective mass #
##################

if rank == 0:

    twop_fold = np.zeros( ( binNum_glob, T_fold ) )
    mEff = np.zeros( ( binNum_glob, T_fold ) )

else:

    twop_fold = None
    mEff = None

comm.Gatherv( twop_fold_loc, [ twop_fold, recvCount * T_fold,
                             recvOffset * T_fold, MPI.DOUBLE ], root=0 )
comm.Gatherv( mEff_loc, [ mEff, recvCount * T_fold,
                          recvOffset * T_fold, MPI.DOUBLE ], root=0 )

if rank == 0:

    # mEff_avg[ t ]

    mEff_avg = np.average( mEff, axis=0 )
    mEff_err = fncs.calcError( mEff, binNum_glob )

    avgOutputFilename = rw.makeFilename( output_template, "mEff_avg" )
    rw.writeAvgDataFile( avgOutputFilename, mEff_avg, mEff_err )

    # Fit the effective mass and two-point functions 

    try:
    
        fitResults = fit.mEffTwopFit( mEff, twop_fold,
                                      rangeEnd, 0, L, tsf,
                                      tsf_t_low_range=[tsf_fitStart],
                                      plat_t_low_range=[plat_fitStart],
                                      checkFit=checkFit )
    
    except fit.lqcdjk_BadFitError as error:
        
        mpi_fncs.mpiPrintErr( "ERROR (lqcdjk_fitting.mEffTwopFit):"
                              + str( error ), comm )

    fitParams = fitResults[ 0 ]
    chiSq = fitResults[ 1 ]
    mEff_fit = fitResults[ 2 ]
    rangeStart = fitResults[ 3 ]
    mEff_rangeStart = fitResults[ 4 ]

    mEffFit_str = "2s" + str( rangeStart ) \
                  + ".2e" + str( rangeEnd )

    if tsf:

        c = fitParams[ :, 0 ]
        E0_mEff = fitParams[ :, 1 ]
        E1_mEff = fitParams[ :, 2 ]

        # Calculate fitted curve

        curve, \
            t_s = fit.calcmEffTwoStateCurve( np.ones( binNum_glob ),
                                             c, E0_mEff, E1_mEff, T,
                                             rangeStart,
                                             rangeEnd )

        curveOutputFilename = rw.makeFilename( output_template,
                                               "mEff_2sf_curve_{}",
                                               mEffFit_str )
        
        c_avg = np.average( c, axis=0 )
        c_err = fncs.calcError( c, binNum_glob )

        E0_mEff_avg = np.average( E0_mEff, axis=0 )
        E0_mEff_err = fncs.calcError( E0_mEff, binNum_glob )

        E1_mEff_avg = np.average( E1_mEff, axis=0 )
        E1_mEff_err = fncs.calcError( E1_mEff, binNum_glob )

        mEff_tsf_outputFilename = rw.makeFilename( output_template,
                                                   "mEff_2sf_{}",
                                                   mEffFit_str )
        rw.writeFitDataFile( mEff_tsf_outputFilename, E0_mEff_avg,
                             E0_mEff_err, rangeStart, rangeEnd )

        chiSqOutputFilename = rw.makeFilename( output_template,
                                               "mEff_2sf_chiSq_{}",
                                               mEffFit_str )

    else: # One-state fit

        c = fitParams[ :, 0 ]
        E0_mEff = fitParams[ :, 1 ]

        # Calculate fitted curve

        curve, t_s = fit.calcTwopOneStateCurve( c, E0_mEff, T,
                                                rangeStart, rangeEnd )

        curveOutputFilename = rw.makeFilename( output_template,
                                               "twop_1sf_curve_{}",
                                               mEffFit_str )
        chiSqOutputFilename = rw.makeFilename( output_template,
                                               "twop_oneStateFit_chiSq_{}",
                                               twopFit_str )

    # End if one-state fit

    #curve_avg = np.average( curve, axis=0 )
    #curve_err = fncs.calcError( curve, binNum_glob )
            
    curve_avg = np.average( curve, axis=0 )
    curve_err = fncs.calcError( curve, binNum_glob )

    chiSq_avg = np.average( chiSq, axis=0 )
    chiSq_err = fncs.calcError( chiSq, binNum_glob )
            
    # Write output files

    rw.writeAvgDataFile_wX( curveOutputFilename, t_s,
                            curve_avg, curve_err )
        
    rw.writeFitDataFile( chiSqOutputFilename, chiSq_avg,
                         chiSq_err, rangeStart, rangeEnd )

    mEff_fit_avg = np.average( mEff_fit, axis=0 )
    mEff_fit_err = fncs.calcError( mEff_fit, binNum_glob )

    mEff_range_str = "2s" + str( mEff_rangeStart ) \
                     + ".2e" + str( rangeEnd )

    mEff_outputFilename = rw.makeFilename( output_template,
                                           "mEff_fit_{}",
                                           mEff_range_str )
    rw.writeFitDataFile( mEff_outputFilename, mEff_fit_avg,
                         mEff_fit_err, mEff_rangeStart, rangeEnd )

# End if first process

comm.Barrier()

# Boosted two-point functions
# twop_boost[ mom, c, t ]

if momSq > 0:

    twop_boost = rw.readTwopFile_zeroQ( twopDir, configList_loc, configNum,
                                        twop_template, srcNum, momSq,
                                        dataFormat, comm )

else:

    twop_boost = np.array( [] )

if rank == 0:
        
    twop_boost_fold_p = np.zeros( ( momBoostNum, binNum_glob, T_fold ) )
    threep_p_jk = np.zeros( ( momBoostNum, flavNum,
                                tsinkNum, binNum_glob, T ) )

else:

    twop_boost_fold_p = np.array( [ None for imom in range( momBoostNum ) ] )
    threep_p_jk = np.array( [ [ [ None for ts in tsink ]
                                  for f in flav_str ]
                                for imom in range( momBoostNum ) ] )

# Loop over momenta
for imom in range( momBoostNum ):

    if momSq > 0:

        #########################################
        # Jackknife boosted two-point functions #
        #########################################

        if binNum_loc:

            twop_boost_jk_loc = fncs.jackknifeBinSubset( twop_boost[ imom ],\
                                                         binSize,
                                                         bin_glob[ rank ] )

            twop_boost_fold_loc = fncs.fold( twop_boost_jk_loc )

        else:

            twop_boost_fold_loc = np.array( [] )

        comm.Gatherv( twop_boost_fold_loc, [ twop_boost_fold_p[ imom ],
                                             recvCount * T_fold,
                                             recvOffset * T_fold,
                                             MPI.DOUBLE ], root=0 )

    # End if non-zero momentum boost
    
    ##############################
    # Read three-point functions #
    ##############################

    # Loop over tsink
    for ts, its in zip( tsink, range( tsinkNum ) ) :
    
        # threep_p[ iflav, c, t ]

        threep_p = rw.getMellinMomentThreep( threepDir, configList_loc,
                                             configNum, threep_tokens,
                                             srcNum, ts, momList[ imom ],
                                             particle, dataFormat, moment,
                                             L, T, comm )

        # Loop over flavor
        for iflav in range( flavNum ):

            # Jackknife
            # threep_p_jk[ iflav, ts, b, t ]

            threep_p_jk_loc = fncs.jackknifeBinSubset( threep_p[ iflav ],
                                                         binSize,
                                                         bin_glob[ rank ] )

            comm.Gatherv( threep_p_jk_loc,
                          [ threep_p_jk[ imom, iflav, its ],
                            recvCount * T,
                            recvOffset * T,
                            MPI.DOUBLE ], root=0 )
            """
            if rank == 0:

                threep_p_avg = np.average( threep_p_jk[ imom, iflav, its ], axis=-2 )
                threep_p_err = fncs.calcError( threep_p_jk[ imom, iflav, its ],
                                                 binNum_glob,
                                                 axis=-2 )

                threep_output_template = "threep_{0}_tsink{1}_{2:+}_{3:+}_{4:+}".format( flav_str[iflav], ts, momList[imom][0], momList[imom][1], momList[imom][2] )

                threep_outFilename = output_template.replace( "*",
                                                              threep_output_template )

                rw.writeAvgDataFile( threep_outFilename,
                                     threep_p_avg,
                                     threep_p_err )
            """
        # End loop over flavor
    # End loop over tsink
# End loop over momenta


####################
# Calculate moment #
####################


if rank == 0:
        
    mellin_p = np.zeros( ( momBoostNum, flavNum, tsinkNum,
                           binNum_glob, T ) )
    #mellin_avgBeforeRatio = np.zeros( ( flavNum, tsinkNum,
    #                                    binNum_glob, T ) )

    c0_p = np.zeros( ( momBoostNum, binNum_glob ) )
    E0_p = np.zeros( ( momBoostNum, binNum_glob ) )

    if tsf:

        c1_p = np.zeros( ( momBoostNum, binNum_glob ) )
        E1_p = np.zeros( ( momBoostNum, binNum_glob ) )

    # mellin_p[ p, flav, ts, b, t ]

    # Loop over momenta
    for imom in range( momBoostNum ):

        # Fit the two-point functions

        if momSq > 0: # Boosted two-point functions
            
            twop_to_fit = twop_boost_fold_p[ imom ]
            mEff_to_fit = pq.mEffFromSymTwop( twop_boost_fold_p[ imom ] )

        else: # Zero momentum two-point functions

            twop_to_fit = twop_fold
            mEff_to_fit = mEff

        if np.any( np.isnan( mEff_to_fit ) ):

            rangeEnd = min(np.where(np.isnan(mEff_to_fit))[-1]) - 1
        """
        if args.twop_fit_start: # fit starts at given t

            twop_rangeStart = args.twop_fit_start

        else: # fit range starts at same t as was used for mEff

            twop_rangeStart = rangeStart

        twopFit_str = "2s" + str( twop_rangeStart ) \
                      + ".2e" + str( rangeEnd )
        """
        fitResults_tmp = fit.mEffTwopFit( mEff_to_fit, twop_to_fit,
                                          rangeEnd, momSq, L, tsf,
                                          tsf_t_low_range=[tsf_fitStart],
                                          plat_t_low_range=[plat_fitStart],
                                          checkFit=checkFit )

        twop_rangeStart = fitResults_tmp[ 3 ]
        
        #twopFit_str = "2s" + str( twop_rangeStart ) \
        #              + ".2e" + str( rangeEnd )

        if tsf:

            fitParams_twop,chiSq=fit.twoStateFit_twop( twop_to_fit,
                                                       twop_rangeStart,
                                                       rangeEnd, T )
            
            c0_p[ imom ] = fitParams_twop[ :, 0 ]
            c1_p[ imom ] = fitParams_twop[ :, 1 ]
            E0_p[ imom ] = fitParams_twop[ :, 2 ]
            E1_p[ imom ] = fitParams_twop[ :, 3 ]

            twop_curve_p, ts_twop = fit.calcTwopTwoStateCurve( c0_p[ imom ], 
                                                               c1_p[ imom ], 
                                                               E0_p[ imom ], 
                                                               E1_p[ imom ], 
                                                               T, twop_rangeStart, 
                                                               rangeEnd )

        else:

            fitParams_twop,chiSq=fit.oneStateFit_twop(twop_to_fit,
                                                      twop_rangeStart,
                                                      rangeEnd, T )

            c0_p[ imom ] = fitParams_twop[ :, 0 ]
            E0_p[ imom ] = fitParams_twop[ :, 1 ]

            twop_curve_p, ts_twop = fit.calcTwopOneStateCurve( c0_p[ imom ], 
                                                               E0_p[ imom ], 
                                                               T, twop_rangeStart, 
                                                               rangeEnd )
        # Average over bins
        
        twop_p_avg = np.average( twop_boost_fold_p[ imom ], axis=-2 )
        twop_p_err = fncs.calcError( twop_boost_fold_p[ imom ],
                                     binNum_glob, axis=-2 )

        twop_curve_p_avg = np.average( twop_curve_p, axis=-2 )
        twop_curve_p_err = fncs.calcError( twop_curve_p,
                                           binNum_glob, axis=-2 )

        # Write twop output file for each momentum
    
        twop_outFilename = rw.makeFilename( output_template,
                                            "twop_{:+}_{:+}_{:+}",
                                            momList[imom][0],
                                            momList[imom][1],
                                            momList[imom][2] )
        rw.writeAvgDataFile( twop_outFilename,
                             twop_p_avg,
                             twop_p_err )

        twop_curve_outFilename = rw.makeFilename( output_template,
                                                  "twop_2sf_curve_{:+}_{:+}_{:+}",
                                                  momList[imom][0],
                                                  momList[imom][1],
                                                  momList[imom][2] )
        rw.writeAvgDataFile_wX( twop_curve_outFilename, ts_twop,
                                twop_curve_p_avg, twop_curve_p_err )

        # Loop over flavor
        for iflav in range( flavNum ):
            # Loop over tsink
            for ts, its in zip( tsink, range( tsinkNum ) ) :
                
                mellin_p[imom,
                         iflav,
                         its]=Z*pq.calcMellin_twopFit( threep_p_jk[imom,
                                                                   iflav,
                                                                   its ],
                                                       ts,E0_mEff,momSq,L,
                                                       c0_p[ imom ],
                                                       E0_p[ imom ], moment )
                """
                # Average over bins

                threep_p_avg = np.average( threep_p_jk[imom,iflav,its],
                                           axis=-2 )
                threep_p_err = fncs.calcError( threep_p_jk[imom,iflav,its],
                                               binNum_glob, axis=-2 )

                mellin_p_avg = np.average( mellin_p[imom,iflav,its],
                                           axis=-2 )
                mellin_p_err = fncs.calcError( mellin_p[imom,iflav,its],
                                               binNum_glob, axis=-2 )

                # Write threep output file for each momentum
    
                threep_outFilename = rw.makeFilename( output_template,
                                                      "{}_threep_{}_tsink{}_"
                                                      + "{:+}_{:+}_{:+}",
                                                      moment_str,
                                                      flav_str[iflav],
                                                      ts,
                                                      momList[imom][0],
                                                      momList[imom][1],
                                                      momList[imom][2] )
                
                rw.writeAvgDataFile( threep_outFilename,
                                     threep_p_avg,
                                     threep_p_err )
                    
                # Write moment output file for each momentum
    
                mellin_outFilename = rw.makeFilename( output_template,
                                                      "{0}_{1}_tsink{2}_"
                                                      + "{3:+}_{4:+}_{5:+}_{6:}",
                                                      moment_str,
                                                      flav_str[iflav],
                                                      ts,
                                                      momList[imom][0],
                                                      momList[imom][1],
                                                      momList[imom][2],
                                                      twopFit_str )
                rw.writeAvgDataFile( mellin_outFilename,
                                     mellin_p_avg,
                                     mellin_p_err )
                """
            # End loop over tsink
        # End loop over flavor
    # End loop over momenta

    # Average over momenta
    # mellin[ flav, ts, b, t ]

    mellin = np.average( mellin_p, axis=0 )
    threep_jk = np.average( threep_p_jk, axis=0 )

    if momSq > 0:

        twop_boost_fold = np.average( twop_boost_fold_p, axis=0 )
        """
        if tsf:

            fitParams_twop_avgBeforeFit, \
                chiSq_avgBeforeFit = fit.twoStateFit_twop( twop_boost_fold,
                                                           twop_rangeStart,
                                                           rangeEnd, T )
            
            c0_avgBeforeFit = fitParams_twop_avgBeforeFit[ :, 0 ]
            c1_avgBeforeFit = fitParams_twop_avgBeforeFit[ :, 1 ]
            E0_avgBeforeFit = fitParams_twop_avgBeforeFit[ :, 2 ]
            E1_avgBeforeFit = fitParams_twop_avgBeforeFit[ :, 3 ]

        else:

            fitParams_twop_avgBeforeFit, \
                chiSq_avgBeforeFit = fit.oneStateFit_twop(twop_boost_fold,
                                                          twop_rangeStart,
                                                          rangeEnd, T )

            c0_avgBeforeFit = fitParams_twop_avgBeforeFit[ :, 0 ]
            E0_avgBeforeFit = fitParams_twop_avgBeforeFit[ :, 1 ]
        """
    c0 = np.average( c0_p, axis=0 )
    E0 = np.average( E0_p, axis=0 )
    """
    # Calculate moment from averaged twop and threep

    # Loop over flavor
    for iflav in range( flavNum ):
        # Loop over tsink
        for ts, its in zip( tsink, range( tsinkNum ) ) :
            
            mellin_avgBeforeRatio[iflav,
                                  its]=Z*pq.calcMellin_twopFit(threep_jk[iflav,
                                                                         its],
                                                               ts,E0_mEff,\
                                                               momSq,L,
                                                               c0, E0, moment )
    """
    # Average over bins
    # mellin_avg[ flav, ts, t ]

    mellin_avg = np.average( mellin, axis=-2 )
    mellin_err = fncs.calcError( mellin, binNum_glob, axis=-2 )

    #mellin_avgBeforeRatio_avg = np.average( mellin_avgBeforeRatio, axis=-2 )
    #mellin_avgBeforeRatio_err = fncs.calcError( mellin_avgBeforeRatio,
    #                                            binNum_glob, axis=-2 )

    threep_avg = np.average( threep_jk, axis=-2 )
    threep_err = fncs.calcError( threep_jk, binNum_glob, axis=-2 )

    if momSq > 0: # Boosted two-point functions
            
        twop_avg = np.average( twop_boost_fold, axis=-2 )
        twop_err = fncs.calcError( twop_boost_fold, binNum_glob, axis=-2 )

    else: # Zero momentum two-point functions

        twop_avg = np.average( twop_fold, axis=-2 )
        twop_err = fncs.calcError( twop_fold, binNum_glob, axis=-2 )

    # Write twop output file
    
    twop_outFilename = rw.makeFilename( output_template, "twop" )
    rw.writeAvgDataFile( twop_outFilename,
                         twop_avg,
                         twop_err )

    # Loop over flavor
    for iflav in range( flavNum ):
        # Loop over tsink
        for ts, its in zip( tsink, range( tsinkNum ) ) :
            
            # Write threep output file
    
            threep_outFilename = rw.makeFilename( output_template,
                                                  "{}_threep_{}_tsink{}",
                                                  moment_str,
                                                  flav_str[ iflav ], ts )

            rw.writeAvgDataFile( threep_outFilename,
                                 threep_avg[ iflav, its ],
                                 threep_err[ iflav, its ] )

            # Write moment output file

            mellin_outFilename \
                = rw.makeFilename( output_template,
                                   "{}_{}_tsink{}",
                                   moment_str, flav_str[ iflav ],
                                   ts )
            rw.writeAvgDataFile( mellin_outFilename, mellin_avg[ iflav, its ],
                                 mellin_err[ iflav, its ] )
            """
            mellin_outFilename \
                = rw.makeFilename( output_template,
                                   "{}_{}_tsink{}_avgBeforeRatio_{}",
                                   moment_str, flav_str[ iflav ],
                                   ts, twopFit_str )
            rw.writeAvgDataFile( mellin_outFilename,
                                 mellin_avgBeforeRatio_avg[ iflav, its ],
                                 mellin_avgBeforeRatio_err[ iflav, its ] )
            """
            ###############
            # Fit plateau #
            ###############

            rangeStart_plat = [ ts // 2 - 1, ts // 2 - 2,
                                ts // 2 - 3, ts // 2 - 4 ]
            
            fitEnd_plat = [ ts // 2 + 1, ts // 2 + 2,
                            ts // 2 + 3, ts // 2 + 4 ]

            # Loop over fit ranges
            for irange in range( len( rangeStart_plat ) ):

                # Fit plateau

                mellin_fit, chiSq = fit.fitPlateau( mellin[ iflav, its ],
                                                    mellin_err[iflav, its ],
                                                    rangeStart_plat[ irange ],
                                                    fitEnd_plat[ irange ] )

                # Average over bins

                mellin_fit_avg = np.average( mellin_fit )
                mellin_fit_err = fncs.calcError( mellin_fit, binNum_glob )
                
                # Write output files

                mellin_fit_outFilename \
                    = rw.makeFilename( output_template,\
                                       "{}_{}_fit_{}_{}_tsink{}",
                                       moment_str,
                                       flav_str[ iflav ],
                                       rangeStart_plat[ irange ],
                                       fitEnd_plat[ irange ],
                                       ts)
                rw.writeFitDataFile( mellin_fit_outFilename, mellin_fit_avg,
                                     mellin_fit_err, rangeStart_plat[ irange ],
                                     fitEnd_plat[ irange ] )
            
            # End loop over fit ranges
        # End loop over tsink
    # End loop over flavor

    exit()
    ##################
    # Two-state Fit  #
    ##################

    if tsf:

        mpi_fncs.mpiPrint( "Will perform the two-state fit", rank )

        # Loop over flavors
        for iflav in range( flavNum ):
            # Loop over number of neglected three-point functions
            for neglect in 2,3:

                ti_to_fit = fncs.initEmptyList( tsinkNum, 1 )

                # Loop over tsinks
                for ts in range( tsinkNum ):

                    ti_to_fit[ ts ] = range( neglect,
                                             tsink[ ts ] - neglect + 1 )
                    """
                    ti_to_fit[ ts ] = np.concatenate( ( range( neglect,
                    tsink[ ts ]
                    - neglect
                    + 1 ),
                    range( tsink[ ts ]
                    + neglect
                    + 5,
                    T -
                    neglect
                    - 5 + 1 ) ) )
                    ti_to_fit[ ts ] = range( tsink[ ts ] + neglect + 5,
                    T - neglect - 5 + 1 )
                    """

                # End loop over tsink

                fitParams = np.zeros( ( momBoostNum, binNum_glob, 7 ) )
                mellin = np.zeros( ( momBoostNum, binNum_glob ) )
                chiSq = np.zeros( ( momBoostNum, binNum_glob ) )

                threep_curve = fncs.initEmptyList( momBoostNum, 1 )
                mellin_curve_const_ts = fncs.initEmptyList( momBoostNum, 1 )
                mellin_curve_const_ti = fncs.initEmptyList( momBoostNum, 1 )
            
                # Loop over momenta
                for imom in range( momBoostNum ):
                
                    fitParams_threep, \
                        chiSq[imom]=fit.twoStateFit_threep(threep_p_jk[imom,
                                                                       iflav],
                                                           ti_to_fit,
                                                           tsink, E0, E1, T )
                    
                    a00 = fitParams_threep[ :, 0 ]
                    a01 = fitParams_threep[ :, 1 ]
                    a11 = fitParams_threep[ :, 2 ]
          
                    # CJL: This needs to be fixed for multi momenta
                    fitParams[ imom ] = np.stack( ( a00, a01, a11,
                                                    c0, c1, E0, E1 ),
                                                  axis=1 )
                
                    # Calculate curve with constant tsink
                    
                    # curve[ p, b, ts, t ]
                    # ti[ ts, t ]

                    threep_curve[ imom ], \
                        ti_threep = fit.calcThreepTwoStateCurve( a00, a01,
                                                                 a11, E0,
                                                                 E1, T,
                                                                 tsink,
                                                                 ti_to_fit,
                                                                 neglect )

                    mellin_curve_const_ts[ imom ], \
                        ti_mellin = fit.calcAvgXTwoStateCurve_const_ts( a00,
                                                                        a01,
                                                                        a11,
                                                                        c0,
                                                                        c1,
                                                                        E0,
                                                                        E1,
                                                                        E0_mEff,
                                                                        momSq,
                                                                        L, T,
                                                                        Z,
                                                                        tsink,
                                                                        ti_to_fit,
                                                                        neglect )

                    mellin_curve_const_ti[ imom ], \
                        ts_mellin = fit.calcAvgXTwoStateCurve_const_ti( a00,
                                                                        a01,
                                                                        a11,
                                                                        c0,
                                                                        c1,
                                                                        E0,
                                                                        E1,
                                                                        E0_mEff,
                                                                        momSq,
                                                                        L, T,
                                                                        Z,
                                                                        tsink[0]-2,
                                                                        tsink[-1]+5 )
                    
                    # mellin[ p, b ]

                    mellin[ imom ] = pq.calcAvgX_twoStateFit( a00, c0,
                                                              E0_mEff,
                                                              momSq,
                                                              L, Z )
                
                # End loop over momenta

                # Average over momenta
                    
                threep_curve = np.average( threep_curve, axis=0 )
            
                mellin_curve_const_ts = np.average( mellin_curve_const_ts,
                                                    axis=0 )
                
                mellin_curve_const_ti = np.average( mellin_curve_const_ti,
                                                    axis=0 )
                
                fitParams = np.average( fitParams, axis=0 )
            
                chiSq = np.average( chiSq, axis=0 )
                
                mellin = np.average( mellin, axis=0 )
    
                # Average over bins
                    
                threep_curve_avg = np.average( threep_curve, axis=0 )
                threep_curve_err = fncs.calcError( threep_curve, binNum_glob )
            
                mellin_curve_const_ts_avg = np.average( mellin_curve_const_ts,
                                                        axis=0 )
                mellin_curve_const_ts_err = fncs.calcError( mellin_curve_const_ts,
                                                            binNum_glob )
                
                mellin_curve_const_ti_avg = np.average( mellin_curve_const_ti,
                                                        axis=0 )
                mellin_curve_const_ti_err = fncs.calcError( mellin_curve_const_ti,
                                                            binNum_glob )
                
                fitParams_avg = np.average( fitParams, axis=0 )
                fitParams_err = fncs.calcError( fitParams, binNum_glob )
                
                chiSq_avg = np.average( chiSq, axis=0 )
                chiSq_err = fncs.calcError( chiSq, binNum_glob )
                
                mellin_avg = np.average( mellin )
                mellin_err = fncs.calcError( mellin, binNum_glob )
    
                # Write output file

                tsf_threep_range_str = mEffFit_str + ".3n" + str( neglect )

                mellinOutputFilename \
                    = rw.makeFilename( output_template,
                                       "{}_{}_2sf_{}_{}",
                                       moment_str,
                                       flav_str[ iflav ],
                                       tsf_threep_range_str,
                                       ts_range_str )
                
                rw.writeFitDataFile( mellinOutputFilename,
                                     mellin_avg, mellin_err, 0, 0 )
                
                chiSqOutputFilename \
                    = rw.makeFilename( output_template,
                                       "{}_{}_2sf_threep_chiSq_{}_{}",
                                       moment_str,
                                       flav_str[ iflav ],
                                       tsf_threep_range_str,
                                       ts_range_str )
        
                rw.writeFitDataFile( chiSqOutputFilename,
                                     chiSq_avg, chiSq_err, 0, 0 )
                
                mellinParamsOutputFilename \
                    = rw.makeFilename( output_template,
                                       "{}_{}_2sf_params_{}_{}",
                                       moment_str,
                                       flav_str[ iflav ],
                                       tsf_threep_range_str,
                                       ts_range_str )

                rw.writeTSFParamsFile( mellinParamsOutputFilename,
                                       fitParams_avg, fitParams_err )
            
                curveOutputFilename \
                    = rw.makeFilename( output_template,
                                       "{}_{}_2sf_curve_{}_{}",
                                       moment_str,
                                       flav_str[ iflav ],
                                       tsf_threep_range_str,
                                       ts_range_str )
                rw.writeAvgDataFile_wX( curveOutputFilename,
                                        ts_mellin,
                                        mellin_curve_const_ti_avg,
                                        mellin_curve_const_ti_err )
                
                for ts in range( tsinkNum ):
            
                    threep_curveOutputFilename \
                        = rw.makeFilename( output_template,
                                           "{}_threep_{}_2sf_curve_tsink{}_{}_{}",
                                           moment_str,
                                           flav_str[ iflav ],
                                           tsink[ ts ],
                                           tsf_threep_range_str,
                                           ts_range_str )
                    rw.writeAvgDataFile_wX( threep_curveOutputFilename,
                                            ti_threep[ ts ],
                                            threep_curve_avg[ ts ],
                                            threep_curve_err[ ts ] )
                    
                    curveOutputFilename \
                        = rw.makeFilename( output_template,
                                           "{}_{}_2sf_curve_tsink{}_{}_{}",
                                           moment_str,
                                           flav_str[ iflav ],
                                           tsink[ ts ],
                                           tsf_threep_range_str,
                                           ts_range_str )
                    rw.writeAvgDataFile_wX( curveOutputFilename,
                                            ti_mellin[ ts ],
                                            mellin_curve_const_ts_avg[ ts ],
                                            mellin_curve_const_ts_err[ ts ] )
            
                # End loop over tsink
            # End loop over number of neglected three-point functions
        # End loop over flavors
    # End if two-state fit
# End if first process
