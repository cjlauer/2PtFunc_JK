from time import time
import h5py
import numpy as np
from os import listdir as ls
from glob import glob
import functions as fncs
import mpi_functions as mpi_fncs
from mpi4py import MPI

# Exception thrown there is an error reading an HDF5 dataset

class lqcdjk_DataSetException(Exception):
    def __init__(self, mismatch):
        Exception.__init__(self, mismatch)


#######################
# HDF5 read functions #
#######################


# Given a source position string, returns the position
# coordinates as a list of integers

# srcGroupName: source postion string to be processed.
#               Should be in the form 'sx#sy#sz#st#',
#               where '#' is an integer.

def getSourcePositions( srcGroupName ):

    # Split string up by 's'

    srcPos = srcGroupName.split( "s" )[ 1: ]

    dims = [ "x", "y", "z", "t" ]

    # Remove label for each dimension so that only the coordinate is left

    srcPos = [ src.replace( d, "" ) for src, d in zip( srcPos, dims ) ]

    return srcPos


# Returns an array of filenames which follow given template
# and are in given directories

# configDir: Head directory which contains sub-directories
# configList: List of sub-directory names
# fn_template: Filename template

def getFileNames( configDir, configList, fn_template ):
    
    configNum = len( configList )

    filename = fncs.initEmptyList( configNum, 1 )

    # Loop through config indices

    for c in range( configNum ):
        
        # Get filenames in sub-directory which follow template

        filename[c] = glob( configDir + "/" + configList[c] \
                            + "/" + fn_template )

        # Check that there are files in sub-directory which follow template

        if filename[c]:

            filename[c] = sorted( filename[c] )

        else:

            print( "WARNING: No files matching " \
                   + fn_template + " were found "\
                   "in " + configDir + "/" + configList[c] )

    # End loop over configs

    return filename


# Checks that dataset name contains all keywords and appends
# it to a list if it does

# dsetnameList: List of dataset names to be appended with dataset
#               names which contain keywords
# dsetname: dataset name to search for keywords
# keyword: Keywords to be searched for in dsetname

def filterDsetname( dsetnameList, dsetname, keyword ):

    if all( kw in dsetname for kw in keyword ):
        dsetnameList.append( dsetname )

    return


# Gets the dataset names in a file. If keyword is supplied, will
# only return datasets names which contain all keywords, else
# returns all datasets names.

# filename: Name of file
# keyword (Optional): Lists of keywords which returned dataset
#                     will contain

def getDatasetNames( filename, *keyword ):
    
    configNum = len( filename )

    # Initialize list of lists with shape [ configNum ][ fileNum ]

    dsetname = fncs.initEmptyList( filename, 2 )

    # Loop through config indices

    for c in range( configNum ):
        
        # Loop through indices of file names in specific config directory

        for fn in range( len( filename[c] ) ): 

            with h5py.File( filename[c][fn], "r" ) as dataFile:
                
                if keyword:
                    
                    # Use filterDsetname() to check if all keywords are
                    # in dsetname[c][fn]
                    
                    dataFile.visititems( lambda name,obj: \
                                         filterDsetname( dsetname[c][fn], \
                                                         name, keyword ) \
                                         if type( obj ) is h5py.Dataset \
                                         else None )

                    # Check that there are any dataset names which contain
                    # all keywords

                    if not dsetname[c][fn]:
                        
                        print( "WARNING: No datasets containing " \
                               "all keywords " + ", ".join( keyword ) \
                               + " in file " \
                               + filename[c][fn] )

                else:

                    # Put all datasets into list

                    dataFile.visititems( lambda name,obj: \
                                         dsetname[c][fn].append(name) \
                                         if type( obj ) is h5py.Dataset \
                                         else None )

            # Close file

            # Ensure that the top groups match across all 
            # files in sub-directory
            
            topGroup_0 = dsetname[c][fn][0].split( "/", 1 )

            for name in dsetname[c][fn]:

                topGroups = name.split( "/", 1 )
            
                assert ( topGroups[0] == topGroup_0[0] ), \
                    "Top groups in configuration " + configList[ c ] \
                    + " do not match" 

        # End loop over filenames

    #End loop over configurations

    return dsetname


# Reads HDF5 datsets containing the given keyword(s) if
# given and returns them as a numpy array. If dsetname
# is given as a keyword argument, only gets datasets
# in dsetname

# configDir: Head directory which contains sub-directories
# configList: List of sub-directory names
# fn_template: Filename template
# keyword (optional): Lists of keywords which returned dataset
#                     will contain
# dsetname (kwarg, optional): List of datasets to read. Overrides
#                             keyword

def getDatasets( configDir, configList, fn_template, *keyword, **kwargs ):
    
    filename = getFileNames( configDir, configList, fn_template )

    configNum = len( filename )

    if "dsetname" in kwargs:

        dsetname = [ [ kwargs[ "dsetname" ] \
                       for fn in range( len( filename[ c ] ) ) ] \
                     for c in range( configNum ) ]

    else:

        dsetname = getDatasetNames( filename, *keyword )

    data = fncs.initEmptyList( dsetname, 3 )

    # Loop over config indices
    for c in range( len( dsetname ) ):
        # Loop over filename indices
        for fn in range( len( dsetname[c] ) ): 
            # Open file
            with h5py.File( filename[c][fn], "r" ) as dataFile:

                # Loop over datasets
                for ds in range( len( dsetname[c][fn] ) ):

                    # Get dataset
                    
                    try:

                        data[c][fn][ds]=np.array(dataFile[dsetname[c][fn][ds]])

                    except Exception as dataSetException:

                        raise lqcdjk_DataSetException( dataSetException )

                # End loop over datasets
            # Close file
        # End loop over files in sub-directory
    # End loop over configs

    return np.array( data )


# Reads HDF5 datsets containing the given keyword(s) if
# given and returns them as a numpy array. Also returns
# a list of the group/dataset names of each dataset.

# configDir: Head directory which contains sub-directories
# configList: List of sub-directory names
# fn_template: Filename template
# keyword (optional): Lists of keywords which returned dataset
#                     will contain
# dsetname (kwarg, optional): List of datasets to read. Overrides
#                             keyword


def getDatasets_wNames( configDir, configList, fn_template, \
                        *keyword, **kwargs ):

    filename = getFileNames( configDir, configList, fn_template )

    configNum = len( filename )

    if "dsetname" in kwargs:

        dsetname = [ [ kwargs[ "dsetname" ] \
                       for fn in range( len( filename[ c ] ) ) ] \
                     for c in range( configNum ) ]
        
    else:

        datasetName = getDatasetNames( filename, *keyword )

    data = fncs.initEmptyList( datasetName, 3 )

    # Loop over config indexes
    for c in range( len( configList ) ):
        
        fileNum = len( filename[ c ] )
    
        sources = set()

        # Loop over filenames
        for fn in range( fileNum ): 
            # Open file
            with h5py.File( filename[ c ][ fn ], "r" ) as dataFile:
                # Loop over datasets
                for ds in range( len( datasetName[c][fn] ) ):

                    # Get dataset

                    data[ c ][ fn ][ ds ] = np.array( dataFile[ datasetName[ c ][ fn ][ ds ] ] )

                    # Get source groups to check that they are unique

                    groups = datasetName[c][fn][ds].split( "/" )

                    sources.add( groups[1] )

                # End loop over datasets
            # Close file
        # End loop over files in sub-directory

        # Ensure that the source (2nd) group is unique to 
        # each file in sub-directory

        assert len( sources ) == fileNum, \
            "Source groups in configuration " \
            + "{} are not unique to file".format( configList[ c ] )

    # End loop over configs

    return np.array( data ), datasetName

# Gets full HDF5 file and returns list of arrays where each 
# array is for a different insertion current. 
# Only supported for files in the GPU format.

# configDir: Head directory which contains sub-directories
# configList: List of sub-directory names
# fn_template: Filename template
# keyword (optional): Lists of keywords which returned dataset
#                     will contain
# dsetname (kwarg, optional): List of datasets to read. Overrides
#                             keyword

def getHDF5File( configDir, configList, fn_template, *keyword, **kwargs ):

    dataset = fncs.initEmptyList( 3, 1 )

    ins_current = [ "noether", "oneD", "ultra_local" ]

    for ic in range( 3 ):

        # Get datasets for this insertion current

        dataset[ ic ] = getDatasets( configDir, configList, \
                                     fn_template, ins_current[ ic ], \
                                     *keyword, **kwargs )

    return dataset


# Gets full HDF5 file and returns list of arrays of datasets 
# and dataset names where each array is for a different insertion
# current. Only supported for files in the GPU format.

# configDir: Head directory which contains sub-directories
# configList: List of sub-directory names
# fn_template: Filename template
# keyword (optional): Lists of keywords which returned dataset
#                     will contain
# dsetname (kwarg, optional): List of datasets to read. Overrides
#                             keyword

def getHDF5File_wNames( configDir, configList, fn_template, \
                        *keyword, **kwargs ):

    dataset = fncs.initEmptyList( 3, 1 )

    datasetName = fncs.initEmptyList( 3, 1 )

    ins_current = [ "noether", "oneD", "ultra_local" ]

    for ic in range( 3 ):

        # Get datasets for this insertion current

        dataset[ ic ], datasetName[ ic ] = getDatasets( configDir, \
                                                        configList, \
                                                        fn_template, \
                                                        ins_current[ ic ], \
                                                        *keyword, **kwargs )

    return dataset, datasetName


def makeFilename( genTemplate, specTemplate, *args ):

    return genTemplate.replace( "*", specTemplate.format( *args ) )


def readMomentaList( corrDir, corr_template, config, particle,
                     srcNum, momSq, dataFormat, mpi_info ):

    momList = []

    if dataFormat == "cpu":

        momList = np.array ( getDatasets( twopDir, [ config ], \
                                          twop_template, \
                                          "twop_".format( particle ), \
                                          "ave{}".format( srcNum ), \
                                          "msq{:0>4}".format( momSq ), \
                                          "mvec" )[ 0, 0, 0, ... ].real, \
                             dtype = int )
    
    else:

        if momSq == 0:

            momList = np.array( [ [ 0, 0, 0 ] ] )

        else:

            pList = getDatasets( twopDir, [ config ], twop_template, 
                                 "Momenta_list" )[ :, 0, 0, ... ]

            pList, pSqList, pSqStart, pSqEnd, pSqWhere = fncs.processMomList( pList )

            ipSq = np.where( pSqList == momSq )[0][0]
            ipSqStart = pSqStart[ ipSq ]
            ipSqEnd = pSqEnd[ ipSq ]

            momList = pList[ 0, ipSqStart : ipSqEnd + 1 ]

    return momList


def readMomentumTransferList( corrDir, corrTemplate, configList,
                             particle, srcNum, pSq, dataFormat, 
                             momentumTransferListFilename, 
                             mpi_info ):

    if momentumTransferListFilename:

        Q = readTxtFile( args.momentumTransferListFilename, dtype=int )

        if dataFormat == "ASCII":
        
            Q = -1.0 * Q

    else:

        if dataFormat == "gpu":

            mpi_fncs.mpiPrint( "No momentum list given, " \
                               + "will read momentum " \
                               + "from correlator files", 
                               mpi_info )

            Q = getDatasets( corrDir, configList, corrTemplate, \
                             "Momenta_list" )[ :, 0, 0, ... ]

        elif dataFormat == "cpu":

            mpi_fncs.mpiPrint( "No momentum list given, " \
                               + "will read momentum " \
                               + "from three-point function files", 
                               mpi_info )

            filename = getFileNames( corrDir, configList, corrTemplate )

            dsetname = getDatasetNames( filename, 
                                        "ave{}".format( srcNum ),
                                        "mvec" )

            # Get first momentum transfer

            Q = getDatasets( corrDir, configList, corrTemplate, 
                             dsetname=[ dsetname[0][0][0] ] )[ 0, 0, 
                                                               0, :, : ]

            # Get the other momentum transfers

            for ds in [ dsetname[ 0 ][ 0 ][ i ] \
                for i in range( 1, len(dsetname[0][0] )) ]:

                dset = getDatasets( corrDir, configList, corrTemplate, 
                                    dsetname=[ds] )[ 0, 0, 0, :, : ]

                Q = np.concatenate( ( Q, dset ), axis=0 )

        elif dataFormat == "ASCII":

            mpi_fncs.mpiPrintError( "ERROR: ASCII format requires a " \
                                    + "momentum list to be given.", 
                                    mpi_info )

        else:

            mpi_fncs.mpiPrintError( "ERROR (readWrite." \
                                    + "readMomentumTransferList): " \
                                    + "Data format {}".format( dataFormat ) \
                                    + " not supported.", 
                                    mpi_info )

    Q = np.array( Q )

    Q, Qsq, Qsq_start, Qsq_end, Qsq_where = fncs.processMomList( Q )

    QNum = len( Q )

    QsqNum = len( Qsq )

    return Q, QNum, Qsq, QsqNum, Qsq_start, Qsq_end, Qsq_where


def readTwopFile_zeroQ( twopDir, configList, configNum, twop_template,
                        srcNum, pSq, dataFormat, mpi_info ):

    comm = mpi_info[ 'comm' ]
    configNum_loc_list = mpi_info[ 'configNum_loc_list' ]
    confOffset = mpi_info[ 'confOffset' ]

    t0 = time()

    if dataFormat == "cpu":

        twop_loc = getDatasets( twopDir, configList, \
                                twop_template, \
                                "ave{}".format( srcNum ), \
                                "msq{:0>4}".format( pSq ), \
                                "arr" )[ :, 0, 0, ... ].real
        
    else:
        
        pList = getDatasets( twopDir, configList, twop_template, 
                             "Momenta_list" )[ :, 0, 0, ... ]

        pList, pSqList, pSqStart, pSqEnd, pSqWhere = fncs.processMomList( pList )

        ipSq = np.where( pSqList == pSq )[0][0]
        ipSqStart = pSqStart[ ipSq ]
        ipSqEnd = pSqEnd[ ipSq ]

        twop_loc = getDatasets( twopDir, configList, \
                                twop_template, \
                                "twop" )[ :, 0, 0, :, 
                                          ipSqStart:ipSqEnd+1, 0 ]

    twop_loc = np.asarray( twop_loc, order='c', dtype=float )

    twop = np.zeros( ( configNum, ) + twop_loc.shape[ 1: ] )
    
    comm.Allgatherv( twop_loc,
                     [ twop,
                       configNum_loc_list \
                       * np.prod( twop_loc.shape[ 1: ] ),
                       confOffset \
                       * np.prod( twop_loc.shape[ 1: ] ),
                       MPI.DOUBLE ] )

    if pSq > 0:

        # twop[ c, t, mom ] -> twop [mom, c, t ]
    
        twop = np.moveaxis( twop, -1, 0 )

    else:

        twop = twop[ ..., 0 ]

    mpi_fncs.mpiPrint( "Read two-point functions from HDF5 files " \
                       + "in {:.3} seconds".format( time() - t0 ), \
                       mpi_info )

    return np.asarray( twop, order='c', dtype=float )


def readTwopFile( twopDir, twop_template, configList, configNum, 
                  Q, Qsq, Qsq_start, Qsq_end, particle, srcNum, pSq,
                  dataFormat, mpi_info ):

    comm = mpi_info[ 'comm' ]
    configNum_loc_list = mpi_info[ 'configNum_loc_list' ]
    confOffset = mpi_info[ 'confOffset' ]

    QNum = len( Q )
    QsqNum = len( Qsq )

    t0 = time()

    if dataFormat == "cpu":

        template = "/twop_{0}/ave{1}/msq{2:0>4}/arr"

        # Get p^2=0 data to determine the size of time dimension

        dataset = [ template.format( particle, srcNum, 0 ) ]

        # twop0[ b, t, q ]

        twop0 = getDatasets( twopDir, configList, twop_template,
                             dsetname=dataset )[:, 0, 0, ... ].real
        
        T = twop0.shape[ -2 ]

        twop_loc = np.zeros( ( len( configList ),
                               QNum, T ) )

        twop_loc[ :, 0, : ] = np.moveaxis( twop0, -1, -2 )[ :, 0, : ]

        # Get p^2>0 data

        for iqsq in range( 1, QsqNum ):

            dataset = [ template.format( particle, srcNum, Qsq[ iqsq ] ) ]

            twop_tmp = getDatasets( twopDir,
                                    configList,
                                    twop_template,
                                    dsetname=dataset )[:, 0, 0, ... ].real

            twop_loc[ :, Qsq_start[ iqsq ] : Qsq_end[ iqsq ] + 1, : ] \
                = np.moveaxis( twop_tmp, -1, -2 )

    elif dataFormat == "ASCII":

        # Determine length of time dimension.
        # 2nd output is not really configuration number because
        # files are not formatted like that.

        T, dummy \
            = detTimestepAndConfigNum(twopDir +
                                      twop_template.replace("*", \
                                                            configList[0]))

        # Get 5th column of two-point files for each configuration

        twop_loc = getTxtData( twopDir,
                               configList,
                               twop_template,
                               dtype=float).reshape( len( configList ),
                                                     QNum, T, 6 )[ ...,
                                                                   4 ]

    else:
        
        twop_loc = getDatasets( twopDir, configList,
                            twop_template,
                            "twop" )[ :, 0, 0, :, :, 0 ]

        # twop_loc[ c, t, Q ]
        # -> twop_loc[ c, Q, t ]

        twop_loc = np.moveaxis( twop_loc, -1, -2 )

    mpi_fncs.mpiPrint( "Read two-point functions from files "
                       + "in {:.3} seconds".format( time() - t0 ), 
                       mpi_info )

    twop_loc = np.asarray( twop_loc, order='c', dtype=float )

    # Gather two-point functions

    twop = np.zeros( ( configNum, ) + twop_loc.shape[ 1: ] )
    
    comm.Allgatherv( twop_loc, [ twop, 
                                 configNum_loc_list
                                 * np.prod( twop_loc.shape[ 1: ] ),
                                 confOffset
                                 * np.prod( twop_loc.shape[ 1: ] ),
                                 MPI.DOUBLE ] )

    return twop


def getMellinMomentThreep( threepDir, configList, configNum, threep_tokens,
                           srcNum, ts, p, particle, dataFormat, moment,
                           L, T, mpi_info, **kwargs ):

    # Get the relevant three-point functions 
    # to calcualte mellin moment of order 1-3 at zero-momentum

    # threepDir: Head directory which contains sub-directories
    # configList: List of sub-directory names
    # configNum: Number of total configurations
    # threep_tokes: Array of filename tokens;
    #               varies depending on data format and particle
    # srcNum: Number of sources
    # ts: Tsink
    # p: Which final momentum to get
    # particle: Which particle to get
    # dataFormat: Which format the data files to be read are in
    # moment: Which mellin moment to get
    # L: Length of lattice space dimensions
    # T: Length of lattice time dimension
    # mpi_info: MPI info dictionary containing communicator
    # dsetname (optional kwarg): List of datasets to read. 
    #                            Overrides keyword

    comm = mpi_info[ 'comm' ]
    configNum_loc_list = mpi_info[ 'configNum_loc_list' ]
    confOffset = mpi_info[ 'confOffset' ]

    threeps = readMellinThreepFile( threepDir, configList, \
                                    threep_tokens, srcNum, ts, p, \
                                    particle, moment, dataFormat, \
                                    T, mpi_info )

    if moment == 1 or moment == "avgX":

        threep_gxDx = threeps[0]
        threep_gyDy = threeps[1]
        threep_gzDz = threeps[2]
        threep_gtDt = threeps[3]
        
        if particle == "kaon":

            threep_s_gxDx = threeps[4]
            threep_s_gyDy = threeps[5]
            threep_s_gzDz = threeps[6]
            threep_s_gtDt = threeps[7]
        
        # Subtract average over directions from gtDt

        threep_loc = threep_gtDt - \
                     0.25 * ( threep_gtDt \
                              + threep_gxDx \
                              + threep_gyDy \
                              + threep_gzDz )

        if particle == "kaon":

            threep_s_loc = threep_s_gtDt - \
                           0.25 * ( threep_s_gtDt \
                                    + threep_s_gxDx \
                                    + threep_s_gyDy \
                                    + threep_s_gzDz )

    elif moment == 2 or moment == "avgX2":

        threep_g0DxDy = threeps[0]
        threep_g0DxDz = threeps[1]
        threep_g0DyDz = threeps[2]
    
        if particle == "kaon":

            threep_s_g0DxDy = threeps[3]
            threep_s_g0DxDz = threeps[4]
            threep_s_g0DyDz = threeps[5]

        # Average over threep_g0DjDk / ( pj * pk )

        nonzeroTerms = 0.0

        for ip in range( 3 ):

            if p[ ip ] * p[ ( ip + 1 ) % 3 ] != 0:

                nonzeroTerms += 1.0
        """
        if comm.Get_rank() == 0:

            print(nonzeroTerms)
            print(p[0],p[1])
            print(threep_g0DxDy)
            print(p[0]*p[1])

            print(p[0],p[2])
            print(threep_g0DxDz)
            print(p[0]*p[2])

            print(p[1],p[2])
            print(threep_g0DyDz)
            print(p[1]*p[2])
        """
        # CJL: I don't do this, but am keeping it in case I need to 
        #      Average over -2 * threep_g0DjDk / ( pj * pk )
        # threep_loc = -2.0 / nonzeroTerms * ( L / 2.0 / np.pi ) ** 2 \

        threep_loc = 1.0 / nonzeroTerms * ( L / 2.0 / np.pi ) ** 2 \
                     * ( threep_g0DxDy \
                         * float( p[ 0 ] \
                                  * p[ 1 ] ) \
                         + threep_g0DxDz \
                         * float( p[ 0 ] \
                                  * p[ 2 ] ) \
                         + threep_g0DyDz \
                         * float( p[ 1 ] \
                                  * p[ 2 ] ) )
        
        if particle == "kaon":

            #threep_loc = -2.0 / nonzeroTerms * ( L / 2.0 / np.pi ) ** 2 
            threep_s_loc = 1.0 / nonzeroTerms * ( L / 2.0 / np.pi ) ** 2 \
                           * ( threep_s_g0DxDy \
                               * float( p[ 0 ] \
                                        * p[ 1 ] )\
                               + threep_s_g0DxDz \
                               * float( p[ 0 ] \
                                        * p[ 2 ] ) \
                               + threep_s_g0DyDz \
                               * float( p[ 1 ] \
                               * p[ 2 ] ) )
        
    elif moment == 3 or moment == "avgX3":

        threep_g0DxDyDz = threeps[0]
    
        if particle == "kaon":

            threep_s_g0DxDyDz = threeps[1]
    
        # Calculate * threep_g0DiDjDk / ( pi* pj * pk )

        threep_loc = ( L / 2.0 / np.pi ) ** 3 \
                     * threep_g0DxDyDz \
                     * float( p[ 0 ] \
                              * p[ 1 ] \
                              * p[ 2 ] )
        
        if particle == "kaon":

            threep_s_loc = ( L / 2.0 / np.pi ) ** 3 \
                           * threep_s_g0DxDyDz \
                           * float( p[ 0 ] \
                                    * p[ 1 ] \
                                    * p[ 2 ] )
        
    else:

        error = "Error (readWrite.getMelinMomentThreep): moment " + moment \
                + " not supported."

        mpi_fncs.mpiPrintError( error, mpi_info )

    threep = np.zeros( ( 1 if particle == "pion" else 2, configNum, T ), \
                       order='c', dtype=float )

    comm.Allgatherv( threep_loc, 
                     [ threep[ 0 ], 
                       configNum_loc_list * np.prod( threep_loc.shape[ 1: ] ),
                       confOffset * np.prod( threep_loc.shape[ 1: ] ),
                       MPI.DOUBLE ] )

    if particle == "kaon":

        comm.Allgatherv( threep_s_loc, 
                         [ threep[ 1 ], 
                           configNum_loc_list * np.prod( threep_s_loc.shape[ 1: ] ),
                           confOffset * np.prod( threep_s_loc.shape[ 1: ] ),
                           MPI.DOUBLE ] )

    return threep

def readMellinThreepFile( threepDir, configList, threep_tokens, srcNum,
                          ts, p, particle, moment, dataFormat,
                          T, mpi_info, **kwargs ):

    comm = mpi_info[ 'comm' ]

    t0 = time()

    # Set filename template

    if dataFormat == "cpu":
        
        if particle == "nucleon":

            threep_template = threep_tokens[ 0 ] + str( ts )

        else:

            threep_template = "{0}{1}{2}{3:+}_{4:+}_{5:+}"
            threep_template = threep_template.format( threep_tokens[ 0 ], \
                                                      ts, threep_tokens[ 1 ],
                                                      p[ 0 ], p[ 1 ], p[ 2 ] )

    else: # Particle is meson

        threep_template = threep_tokens[0]

    if particle == "nucleon":

        if moment == 1 or moment == "avgX":
                
            if dataFormat == "cpu":

                threeps = readNucleonAvgXFile_cpu( threepDir, 
                                                   threep_template,
                                                   configList, ts )

            else:

                error = "Error (readWrite.readMellinThreepFile): " \
                        + "GPU format not supported for nucleon."
                mpi_fncs.mpiPrintError( error, mpi_info )

        else:

            error = "Error (readWrite.readMellinThreepFile): " \
                    + "moments of order >1 not supported for nucleon."
            mpi_fncs.mpiPrintError( error, mpi_info )

    else: # Particle is meson

        if dataFormat == "cpu":

            if moment == 1 or moment == "avgX":

                threeps = readMesonAvgXFile_cpu( threepDir,
                                                 threep_template,
                                                 configList,
                                                 particle, ts, 
                                                 srcNum, mpi_info )

            elif moment == 2 or moment == "avgX2":

                threeps = readMesonAvgX2File_cpu( threepDir,
                                                  threep_template,
                                                  configList,
                                                  particle, ts, 
                                                  srcNum, mpi_info )
                
            elif moment == 3 or moment == "avgX3":

                threeps = readMesonAvgX3File_cpu( threepDir,
                                                  threep_template,
                                                  configList,
                                                  particle, ts, 
                                                  srcNum, mpi_info )

            else:
                
                error = "Error (readWrite.readMellinThreepFile): " \
                        + "moments of order >3 not supported."
                mpi_fncs.mpiPrintError( error, mpi_info )
                

        elif dataFormat == "gpu":

            if moment == 1 or moment == "avgX":

                threeps = readMesonAvgXFile_gpu( threepDir,
                                                 threep_template,
                                                 configList, particle, 
                                                 ts, mpi_info )

            else:

                error = "Error (readWrite.readMellinThreepFile): " \
                        + "moments of order >1 not supported for " \
                        + dataFormat + " data format."
                mpi_fncs.mpiPrintError( error, mpi_info )
    
    threeps = np.pad( threeps, ( ( 0, 0 ), ( 0, 0 ), \
                                 ( 0, T - threeps.shape[ -1 ] ) ), \
                      'constant', \
                      constant_values=( 0.0, 0.0 ) )

    mpi_fncs.mpiPrint( "Read three-point functions from HDF5 files " \
                       + "in {:.3} seconds".format( time() - t0 ), \
                       mpi_info )

    return np.asarray( threeps, order='c', dtype=float )


def readMesonAvgXFile_cpu( threepDir, threep_template, configList, \
                           particle, ts, srcNum, mpi_info ):

    filename = threep_template + ".up.h5"

    dsetname_pre = "/thrp/ave{}/dt{}/up/".format( srcNum, ts )

    dsetname_post = "/msq0000/arr"
            
    threep_gtDt = getDatasets( threepDir, \
                               configList, \
                               filename, \
                               dsetname=[ dsetname_pre \
                                          + "=der:g0D0:sym=" \
                                          + dsetname_post])[:,0,0,:,0].real
    threep_gxDx = getDatasets( threepDir, \
                               configList, \
                               filename, \
                               dsetname=[dsetname_pre \
                                         +"=der:gxDx:sym=" \
                                         +dsetname_post])[:,0,0,:,0].real
    threep_gyDy = getDatasets( threepDir, \
                               configList, \
                               filename, \
                               dsetname=[dsetname_pre \
                                         +"=der:gyDy:sym=" \
                                         +dsetname_post])[:,0,0,:,0].real
    threep_gzDz = getDatasets( threepDir, \
                               configList, \
                               filename, \
                               dsetname=[dsetname_pre \
                                         +"=der:gzDz:sym=" \
                                         +dsetname_post])[:,0,0,:,0].real
                
    if particle == "kaon":
            
        filename_s = threep_template + ".strange.h5"

        dsetname_s_pre = "/thrp/ave{}/dt{}/strange/".format( srcNum, \
                                                             ts )

        threep_s_gtDt=getDatasets(threepDir, \
                                  configList, \
                                  filename_s, \
                                  dsetname=[dsetname_s_pre \
                                            +"=der:g0D0:sym=" \
                                            +dsetname_post])[:,0,0,:,0].real
        threep_s_gxDx=getDatasets(threepDir, \
                                  configList, \
                                  filename_s, \
                                  dsetname=[dsetname_s_pre \
                                            +"=der:gxDx:sym=" \
                                            +dsetname_post])[:,0,0,:,0].real
        threep_s_gyDy=getDatasets(threepDir, \
                                  configList, \
                                  filename_s, \
                                  dsetname=[dsetname_s_pre \
                                            +"=der:gyDy:sym=" \
                                            +dsetname_post])[:,0,0,:,0].real
        threep_s_gzDz=getDatasets(threepDir, \
                                  configList, \
                                  filename_s, \
                                  dsetname=[dsetname_s_pre \
                                            +"=der:gzDz:sym=" \
                                            +dsetname_post])[:,0,0,:,0].real

        return np.array( [ threep_gxDx, threep_gyDy, \
                           threep_gzDz, threep_gtDt, \
                           threep_s_gxDx, threep_s_gyDy, \
                           threep_s_gzDz, threep_s_gtDt ] )
        
    elif particle == "pion": 

        return np.array( [ threep_gxDx, threep_gyDy, \
                           threep_gzDz, threep_gtDt ] )
        
    else: 
        
        error = "Error (readwrite.readMesonAvgXFile_cpu): Particle " \
                + particle + " not supported."
        mpi_fncs.mpiPrintError( error, mpi_info )


def readMesonAvgXFile_gpu( threepDir, threep_template, configList, \
                           particle, ts, mpi_info ):

    threep_gxDx = getDatasets( threepDir, \
                               configList, \
                               threep_template, \
                               "tsink_" + str( ts ), \
                               "oneD", \
                               "dir_00", \
                               "up", \
                               "threep" )[ :, 0, 0, ..., 0, 1, 0 ]

    threep_gyDy = getDatasets( threepDir, \
                               configList, \
                               threep_template, \
                               "tsink_" + str( ts ), \
                               "oneD", \
                               "dir_01", \
                               "up", \
                               "threep" )[ :, 0, 0, ..., 0, 2, 0 ]
    
    threep_gzDz = getDatasets( threepDir, \
                               configList, \
                               threep_template, \
                               "tsink_" + str( ts ), \
                               "oneD", \
                               "dir_02", \
                               "up", \
                               "threep" )[ :, 0, 0, ..., 0, 3, 0 ]

    threep_gtDt = getDatasets( threepDir, \
                               configList, \
                               threep_template, \
                               "tsink_" + str( ts ), \
                               "oneD", \
                               "dir_03", \
                               "up", \
                               "threep" )[ :, 0, 0, ..., 0, 4, 0 ]

    threep_s_gxDx = np.array( [] )
            
    threep_s_gyDy = np.array( [] )
                
    threep_s_gzDz = np.array( [] )
    
    threep_s_gtDt = np.array( [] )

    if particle == "kaon":
            
        threep_s_gxDx = getDatasets( threepDir, \
                                     configList, \
                                     threep_template, \
                                     "tsink_" + str( ts ), \
                                     "oneD", \
                                     "dir_00", \
                                     "strange", \
                                     "threep" )[ :, 0, 0, ..., 0, 1, 0 ]
                    
        threep_s_gyDy = getDatasets( threepDir, \
                                     configList, \
                                     threep_template, \
                                     "tsink_" + str( ts ), \
                                     "oneD", \
                                     "dir_01", \
                                     "strange", \
                                     "threep" )[ :, 0, 0, ..., 0, 2, 0 ]
                    
        threep_s_gzDz = getDatasets( threepDir, \
                                     configList, \
                                     threep_template, \
                                     "tsink_" + str( ts ), \
                                     "oneD", \
                                     "dir_02", \
                                     "strange", \
                                     "threep" )[ :, 0, 0, ..., 0, 3, 0 ]
                    
        threep_s_gtDt = getDatasets( threepDir, \
                                     configList, \
                                     threep_template, \
                                     "tsink_" + str( ts ), \
                                     "oneD", \
                                     "dir_03", \
                                     "strange", \
                                     "threep" )[ :, 0, 0, ..., 0, 4, 0 ]
                    
        return np.array( [ threep_gxDx, threep_gyDy, \
                              threep_gzDz, threep_gtDt, \
                              threep_s_gxDx, threep_s_gyDy, \
                              threep_s_gzDz, threep_s_gtDt ] )

    elif particle == "pion": 

        return np.array( [ threep_gxDx, threep_gyDy, \
                              threep_gzDz, threep_gtDt ] )

    else: 

        error = "Error (readWrite.readMesonsAvgXFile_gpu): Particle " \
                + particle + " not supported."
        
        mpi_fncs.mpiPrintError( error, mpi_info )


def readNucleonAvgXFile_cpu( threepDir, threep_template, configList, \
                             particle, ts ):

    filename = threep_template + ".up.h5"

    threep_u_gxDx = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:gxDx:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real

    threep_u_gyDy = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:gyDy:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real

    threep_u_gzDz = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:gzDz:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real

    threep_u_gtDt = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:g0D0:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real

    filename = threep_template + str( ts ) + ".dn.h5"

    threep_d_gxDx = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:gxDx:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real

    threep_d_gyDy = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:gyDy:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real

    threep_d_gzDz = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:gzDz:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real
                
    threep_d_gtDt = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 "=der:g0D0:sym=", \
                                 "msq0000", \
                                 "arr" )[ :, 0, 0, :, 0 ].real
    
    threep_gxDx = threep_u_gxDx - threep_d_gxDx
                
    threep_gyDy = threep_u_gyDy - threep_d_gyDy

    threep_gzDz = threep_u_gzDz - threep_d_gzDz

    threep_gtDt = threep_u_gtDt - threep_d_gtDt

    return np.array( [ threep_gxDx, threep_gyDy, \
                       threep_gzDz, threep_gtDt ] )


def readMesonAvgX2File_cpu( threepDir, threep_template, configList, \
                            particle, ts, srcNum, mpi_info ):
    
    filename = threep_template + ".up.h5"

    dsetname_pre = "/thrp/ave{}/dt{}/up/".format( srcNum, ts )

    dsetname_post = "/msq0000/arr"

    try:

        threep_g0DxDy = getDatasets( threepDir, \
                                     configList, \
                                     filename, \
                                     dsetname=[ dsetname_pre \
                                                + "der2:g0DxDy" \
                                                + dsetname_post])[:,0,0,\
                                                                  :,0].real

    except lqcdjk_DataSetException as dataSetException:

        dsetname_pre = "/thrp/ave{}/P0/dt{}/up/".format( srcNum, ts )

        threep_g0DxDy = getDatasets( threepDir, \
                                     configList, \
                                     filename, \
                                     dsetname=[ dsetname_pre \
                                                + "der2:g0DxDy" \
                                                + dsetname_post])[:,0,0,\
                                                                  :,0].real

    threep_g0DxDz = getDatasets( threepDir, \
                                 configList, \
                                 filename, \
                                 dsetname=[ dsetname_pre \
                                            + "der2:g0DxDz" \
                                            + dsetname_post])[:,0,0,\
                                                              :,0].real

    threep_g0DyDz= getDatasets( threepDir, \
                                configList, \
                                filename, \
                                dsetname=[ dsetname_pre \
                                           + "der2:g0DyDz" \
                                           + dsetname_post ] )[:,0,0,\
                                                               :,0].real

    if particle == "kaon":
            
        filename_s = threep_template + ".strange.h5"

        if "P0" in dsetname_pre:

            dsetname_s_pre = "/thrp/ave{}/P0/dt{}/strange/".format( srcNum, ts )

        else:

            dsetname_s_pre = "/thrp/ave{}/dt{}/strange/".format( srcNum, ts )

        threep_s_g0DxDy = getDatasets( threepDir, \
                                       configList, \
                                       filename_s, \
                                       dsetname=[dsetname_s_pre \
                                                 +"der2:g0DxDy" \
                                                 +dsetname_post])[:,0,0,\
                                                                  :,0].real
        threep_s_g0DxDz = getDatasets( threepDir, \
                                       configList, \
                                       filename_s, \
                                       dsetname=[dsetname_s_pre \
                                                 +"der2:g0DxDz" \
                                                 +dsetname_post])[:,0,0,\
                                                                  :,0].real
        threep_s_g0DyDz = getDatasets( threepDir, \
                                       configList, \
                                       filename_s, \
                                       dsetname=[dsetname_s_pre \
                                                 +"der2:g0DyDz" \
                                                 +dsetname_post])[:,0,0,\
                                                                  :,0].real

        return np.array( [ threep_g0DxDy, threep_g0DxDz, \
                           threep_g0DyDz, \
                           threep_s_g0DxDy, threep_s_g0DxDz, \
                           threep_s_g0DyDz ] )

    elif particle == "pion": 

        return np.array( [ threep_g0DxDy, threep_g0DxDz, \
                           threep_g0DyDz ] )

    else: 

        mpi_fncs.mpiPrintError( "Error (readWrite.readMesonAvgX2File_cpu): " \
                              + "Particle " + particle + " not supported.", \
                              mpi_info )


def readMesonAvgX3File_cpu( threepDir, threep_template, configList, \
                            particle, ts, srcNum, mpi_info ):
    
    filename = threep_template + ".up.h5"

    dsetname = "/thrp/ave{}/dt{}".format( srcNum, ts ) \
               + "/up/der3:g0DxDyDz/msq0000/arr"

    try:

        threep = getDatasets( threepDir, \
                              configList, \
                              filename, \
                              dsetname=[dsetname])[:,0,0,:,0].imag

    except lqcdjk_DataSetException as dataSetException:

        dsetname = "/thrp/ave{}/P0/dt{}".format( srcNum, ts ) \
                   + "/up/der3:g0DxDyDz/msq0000/arr"

        threep = getDatasets( threepDir, \
                              configList, \
                              filename, \
                              dsetname=[dsetname])[:,0,0,:,0].imag

    if particle == "kaon":
            
        filename_s = threep_template + ".strange.h5"

        if "P0" in dsetname:

            dsetname_s = "/thrp/ave{}/P0/dt{}".format( srcNum, ts ) \
                         + "/strange/der3:g0DxDyDz/msq0000/arr"

        else:

            dsetname_s = "/thrp/ave{}/dt{}".format( srcNum, ts ) \
                         + "/strange/der3:g0DxDyDz/msq0000/arr"

        threep_s = getDatasets( threepDir, \
                                configList, \
                                filename_s, \
                                dsetname=[dsetname_s])[:,0,0,:,0].imag
                
        return np.array( [ threep, threep_s ] )

    elif particle == "pion":

        return np.array( [ threep ] )

    else: 

        mpi_fncs.mpiPrintError( "Error (readAvgX2File): Particle " \
                              + particle + " not supported.", mpi_info )


def readAvgXFile( threepDir, configList, threep_tokens, srcNum, \
                  ts, momList, particle, dataFormat, T, mpi_info, **kwargs ):

    t0 = time()

    # Set filename template

    if dataFormat == "cpu" and particle == "meson":
        
        threep_template = "{0}{1}{2}{3:+}_{4:+}_{5:+}"
        threep_template = threep_template.format( threep_tokens[ 0 ], \
                                                  ts, threep_tokens[ 1 ], \
                                                  p[ 0 ], p[ 1 ], p[ 2 ] )

    else:

        threep_template = threep_tokens[0]

    if particle == "nucleon":

        if dataFormat == "cpu":

            filename_u_gxDx = threep_template + str( ts ) + ".up.h5"

            threep_u_gxDx = getDatasets( threepDir, \
                                         configList, \
                                         filename_u_gxDx, \
                                         "=der:gxDx:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gyDy = threep_template + str( ts ) + ".up.h5"

            threep_u_gyDy = getDatasets( threepDir, \
                                         configList, \
                                         filename_u_gyDy, \
                                         "=der:gyDy:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gzDz = threep_template + str( ts ) + ".up.h5"
            
            threep_u_gzDz = getDatasets( threepDir, \
                                         configList, \
                                         filename_u_gzDz, \
                                         "=der:gzDz:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gtDt = threep_template + str( ts ) + ".up.h5"

            threep_u_gtDt = getDatasets( threepDir, \
                                         configList, \
                                         filename_u_gtDt, \
                                         "=der:g0D0:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gxDx = threep_template + str( ts ) + ".dn.h5"

            threep_d_gxDx = getDatasets( threepDir, \
                                         configList, \
                                         filename_d_gxDx, \
                                         "=der:gxDx:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gyDy = threep_template + str( ts ) + ".dn.h5"

            threep_d_gyDy = getDatasets( threepDir, \
                                         configList, \
                                         filename_d_gyDy, \
                                         "=der:gyDy:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gzDz = threep_template + str( ts ) + ".dn.h5"
                
            threep_d_gzDz = getDatasets( threepDir, \
                                         configList, \
                                         filename_d_gzDz, \
                                         "=der:gzDz:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gtDt = threep_template + str( ts ) + ".dn.h5"

            threep_d_gtDt = getDatasets( threepDir, \
                                         configList, \
                                         filename_d_gtDt, \
                                         "=der:g0D0:sym=", \
                                         "msq0000", \
                                         "arr" )[ :, 0, 0, :, 0 ].real
            
            threep_gxDx = threep_u_gxDx - threep_d_gxDx
                
            threep_gyDy = threep_u_gyDy - threep_d_gyDy

            threep_gzDz = threep_u_gzDz - threep_d_gzDz

            threep_gtDt = threep_u_gtDt - threep_d_gtDt

            threeps = np.array( [ threep_gxDx, threep_gyDy, \
                                  threep_gzDz, threep_gtDt ] )

        else:

            error = "Error (readWrite.readAvgXFile): GPU format not supported for nucleon."
            
            mpi_fncs.mpiPrintError( error, mpi_info )

    else: # Particle is meson

        if dataFormat == "gpu":

            threep_gxDx = getDatasets( threepDir, \
                                       configList, \
                                       threep_template, \
                                       "tsink_" + str( ts ), \
                                       "oneD", \
                                       "dir_00", \
                                       "up", \
                                       "threep" )[ :, 0, 0, ..., 0, 1, 0 ]

            threep_gyDy = getDatasets( threepDir, \
                                       configList, \
                                       threep_template, \
                                       "tsink_" + str( ts ), \
                                       "oneD", \
                                       "dir_01", \
                                       "up", \
                                       "threep" )[ :, 0, 0, ..., 0, 2, 0 ]
    
            threep_gzDz = getDatasets( threepDir, \
                                       configList, \
                                       threep_template, \
                                       "tsink_" + str( ts ), \
                                       "oneD", \
                                       "dir_02", \
                                       "up", \
                                       "threep" )[ :, 0, 0, ..., 0, 3, 0 ]

            threep_gtDt = getDatasets( threepDir, \
                                       configList, \
                                       threep_template, \
                                       "tsink_" + str( ts ), \
                                       "oneD", \
                                       "dir_03", \
                                       "up", \
                                       "threep" )[ :, 0, 0, ..., 0, 4, 0 ]

            threep_s_gxDx = np.array( [] )
            
            threep_s_gyDy = np.array( [] )
        
            threep_s_gzDz = np.array( [] )
    
            threep_s_gtDt = np.array( [] )

            if particle == "kaon":
            
                threep_s_gxDx = getDatasets( threepDir, \
                                             configList, \
                                             threep_template, \
                                             "tsink_" + str( ts ), \
                                             "oneD", \
                                             "dir_00", \
                                             "strange", \
                                             "threep" )[ :, 0, 0, ..., \
                                                         0, 1, 0 ]
                
                threep_s_gyDy = getDatasets( threepDir, \
                                             configList, \
                                             threep_template, \
                                             "tsink_" + str( ts ), \
                                             "oneD", \
                                             "dir_01", \
                                             "strange", \
                                             "threep" )[ :, 0, 0, ..., \
                                                         0, 2, 0 ]
    
                threep_s_gzDz = getDatasets( threepDir, \
                                             configList, \
                                             threep_template, \
                                             "tsink_" + str( ts ), \
                                             "oneD", \
                                             "dir_02", \
                                             "strange", \
                                             "threep" )[ :, 0, 0, ..., \
                                                         0, 3, 0 ]

                threep_s_gtDt = getDatasets( threepDir, \
                                             configList, \
                                             threep_template, \
                                             "tsink_" + str( ts ), \
                                             "oneD", \
                                             "dir_03", \
                                             "strange", \
                                             "threep" )[ :, 0, 0, ..., \
                                                         0, 4, 0 ]
            
                threeps = np.array( [ threep_gxDx, threep_gyDy, \
                                      threep_gzDz, threep_gtDt, \
                                      threep_s_gxDx, threep_s_gyDy, \
                                      threep_s_gzDz, threep_s_gtDt ] )

            elif particle == "pion": 

                threeps = np.array( [ threep_gxDx, threep_gyDy, \
                                      threep_gzDz, threep_gtDt ] )

            else: 

                print( "Error (readAvgXFile): Particle " \
                    + particle + " not supported." )

                exit()                

        elif dataFormat == "cpu":

            filename = threep_template + ".up.h5"

            dsetname_pre = "/thrp/ave{}/dt{}/up/".format( srcNum, ts )

            dsetname_insertion = [ "=der:g0D0:sym=", \
                                   "=der:gxDx:sym=", \
                                   "=der:gyDy:sym=", \
                                   "=der:gzDz:sym=" ]

            dsetname_post = "/msq0000/arr"
            
            threep_gtDt = getDatasets( threepDir, \
                                       configList, \
                                       filename, \
                                       dsetname=[ dsetname_pre \
                                       + dsetname_insertion[ 0 ] \
                                       + dsetname_post ] )[ :, 0, 0, \
                                                            :, 0 ].real
            threep_gxDx = getDatasets( threepDir, \
                                       configList, \
                                       filename, \
                                       dsetname=[ dsetname_pre \
                                       + dsetname_insertion[ 1 ] \
                                       + dsetname_post ] )[ :, 0, 0, \
                                                            :, 0 ].real
            threep_gyDy= getDatasets( threepDir, \
                                       configList, \
                                       filename, \
                                       dsetname=[ dsetname_pre \
                                       + dsetname_insertion[ 2 ] \
                                       + dsetname_post ] )[ :, 0, 0, \
                                                            :, 0 ].real
            threep_gzDz = getDatasets( threepDir, \
                                       configList, \
                                       filename, \
                                       dsetname=[ dsetname_pre \
                                       + dsetname_insertion[ 3 ] \
                                       + dsetname_post ] )[ :, 0, 0, \
                                                            :, 0 ].real

            if particle == "kaon":
            
                filename_s = threep_template + ".strange.h5"

                dsetname_s_pre = "/thrp/ave{}/dt{}/strange/".format( srcNum, ts )

                threep_s_gtDt = getDatasets( threepDir, \
                                             configList, \
                                             filename_s, \
                                             dsetname=[ dsetname_s_pre \
                                                        + dsetname_insertion[ 0 ] \
                                                        + dsetname_post ] )[ :, 0, 0, :, 0 ].real
                threep_s_gxDx = getDatasets( threepDir, \
                                             configList, \
                                             filename_s, \
                                             dsetname=[ dsetname_s_pre \
                                                        + dsetname_insertion[ 1 ] \
                                                        + dsetname_post ] )[ :, 0, 0, :, 0 ].real
                threep_s_gyDy= getDatasets( threepDir, \
                                            configList, \
                                            filename_s, \
                                            dsetname=[ dsetname_s_pre \
                                                       + dsetname_insertion[ 2 ] \
                                                       + dsetname_post ] )[ :, 0, 0, :, 0 ].real
                threep_s_gzDz = getDatasets( threepDir, \
                                             configList, \
                                             filename_s, \
                                             dsetname=[ dsetname_s_pre \
                                                        + dsetname_insertion[ 3 ] \
                                                        + dsetname_post ] )[ :, 0, 0, :, 0 ].real

                threeps = np.array( [ threep_gxDx, threep_gyDy, \
                                      threep_gzDz, threep_gtDt, \
                                      threep_s_gxDx, threep_s_gyDy, \
                                      threep_s_gzDz, threep_s_gtDt ] )

            elif particle == "pion": 

                threeps = np.array( [ threep_gxDx, threep_gyDy, \
                                      threep_gzDz, threep_gtDt ] )

            else: 

                print( "Error (readAvgXFile): Particle " \
                       + particle + " not supported." )

                exit()                

    mpi_fncs.mpiPrint( "Read three-point functions from HDF5 files " \
                       + "in {:.3} seconds".format( time() - t0 ), \
                       mpi_info )

    threeps = np.pad( threeps, ( ( 0, 0 ), ( 0, 0 ), \
                                 ( 0, T - threeps.shape[ -1 ] ) ), \
                      'constant', \
                      constant_values=( 0.0, 0.0 ) )

    return np.asarray( threeps, order='c', dtype=float )

# Get the real part of gxDx, gyDy, gzDz, and gtDt
# three-point functions at zero-momentum

# threepDir: Head directory which contains sub-directories
# configList: List of sub-directory names
# threep_template: Filename template
# ts: Tsink
# particle: Which particle to do
# dataFormat: Which format the data files to be read are in
# dsetname (kwarg, optional): List of datasets to read. Overrides
#                             keyword

def readAvgX2File( threepDir, configList, threep_tokens, srcNum, \
                   ts, p, particle, dataFormat, T, mpi_info, **kwargs ):

    t0 = time()

    # Set filename template

    if dataFormat == "cpu":
        
        threep_template = "{0}{1}{2}{3:+}_{4:+}_{5:+}"
        threep_template = threep_template.format( threep_tokens[ 0 ], \
                                                  ts, threep_tokens[ 1 ], \
                                                  p[ 0 ], p[ 1 ], p[ 2 ] )

    else:

        error = "Error (readWrite.readAvgX2File): GPU format not supported"

        mpi_fncs.mpiPrintError( error, mpi_info )

    if particle == "nucleon":
        """
        if dataFormat == "cpu":

            filename_u_gxDx = threep_template + str( ts ) + ".up.h5"

            threep_u_gxDx = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gxDx, \
                                            "=der:gxDx:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gyDy = threep_template + str( ts ) + ".up.h5"

            threep_u_gyDy = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gyDy, \
                                            "=der:gyDy:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gzDz = threep_template + str( ts ) + ".up.h5"

            threep_u_gzDz = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gzDz, \
                                            "=der:gzDz:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gtDt = threep_template + str( ts ) + ".up.h5"

            threep_u_gtDt = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gtDt, \
                                            "=der:g0D0:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gxDx = threep_template + str( ts ) + ".dn.h5"

            threep_d_gxDx = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gxDx, \
                                            "=der:gxDx:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gyDy = threep_template + str( ts ) + ".dn.h5"

            threep_d_gyDy = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gyDy, \
                                            "=der:gyDy:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gzDz = threep_template + str( ts ) + ".dn.h5"

            threep_d_gzDz = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gzDz, \
                                            "=der:gzDz:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gtDt = threep_template + str( ts ) + ".dn.h5"

            threep_d_gtDt = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gtDt, \
                                            "=der:g0D0:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real
            
            threep_gxDx = threep_u_gxDx - threep_d_gxDx

            threep_gyDy = threep_u_gyDy - threep_d_gyDy

            threep_gzDz = threep_u_gzDz - threep_d_gzDz

            threep_gtDt = threep_u_gtDt - threep_d_gtDt

            return [ threep_gxDx, threep_gyDy, threep_gzDz, threep_gtDt ]

        else:

            print( "GPU format not supported for nucleon, yet." )

            exit()
        """
        mpi_fncs.mpiPrintError( "Error (readWrite.readAvgX2File): " \
                                + "Nucleon not supported", mpi_info )
    else: # Particle is meson
        
        if dataFormat == "gpu":
            """
            threep_gxDx = getDatasets( threepDir, \
                                          configList, \
                                          threep_template, \
                                          "tsink_" + str( ts ), \
                                          "oneD", \
                                          "dir_00", \
                                          "up", \
                                          "threep" )[ :, 0, 0, ..., 0, 1, 0 ]

            threep_gyDy = getDatasets( threepDir, \
                                          configList, \
                                          threep_template, \
                                          "tsink_" + str( ts ), \
                                          "oneD", \
                                          "dir_01", \
                                          "up", \
                                          "threep" )[ :, 0, 0, ..., 0, 2, 0 ]
    
            threep_gzDz = getDatasets( threepDir, \
                                          configList, \
                                          threep_template, \
                                          "tsink_" + str( ts ), \
                                          "oneD", \
                                          "dir_02", \
                                          "up", \
                                          "threep" )[ :, 0, 0, ..., 0, 3, 0 ]

            threep_gtDt = getDatasets( threepDir, \
                                       configList, \
                                       threep_template, \
                                       "tsink_" + str( ts ), \
                                       "oneD", \
                                       "dir_03", \
                                       "up", \
                                       "threep" )[ :, 0, 0, ..., 0, 4, 0 ]

            threep_s_gxDx = np.array( [] )
            
            threep_s_gyDy = np.array( [] )
        
            threep_s_gzDz = np.array( [] )
    
            threep_s_gtDt = np.array( [] )

            if particle == "kaon":
            
                threep_s_gxDx = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_00", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 1, 0 ]

                threep_s_gyDy = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_01", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 2, 0 ]
    
                threep_s_gzDz = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_02", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 3, 0 ]

                threep_s_gtDt = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_03", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 4, 0 ]
            
                return [ threep_gxDx, threep_gyDy, \
                         threep_gzDz, threep_gtDt, \
                         threep_s_gxDx, threep_s_gyDy, \
                         threep_s_gzDz, threep_s_gtDt ]

            elif particle == "pion": 

                return [ threep_gxDx, threep_gyDy, \
                         threep_gzDz, threep_gtDt ]

            else: 

                print( "Error (readAvgXFile): Particle " \
                    + particle + " not supported." )

                exit()                
            """
            mpi_fncs.mpiPrintError( "Error (readWrite.readAvgX2File): " \
                                    + "GPU format not supported, yet.", \
                                    mpi_info )

        elif dataFormat == "cpu":

            filename = threep_template + ".up.h5"

            dsetname_pre = "/thrp/ave{}/P0/dt{}/up/".format( srcNum, ts )

            dsetname_insertion = [ "der2:g0DxDy", \
                                   "der2:g0DxDz", \
                                   "der2:g0DyDz" ]

            dsetname_post = "/msq0000/arr"

            threep_g0DxDy = getDatasets( threepDir, \
                                         configList, \
                                         filename, \
                                         dsetname=[ dsetname_pre \
                                                    + dsetname_insertion[ 0 ] \
                                                    + dsetname_post])[:,0,0, \
                                                                      :,0].real
            threep_g0DxDz = getDatasets( threepDir, \
                                         configList, \
                                         filename, \
                                         dsetname=[ dsetname_pre \
                                                    + dsetname_insertion[ 1 ] \
                                                    + dsetname_post])[:,0,0, \
                                                                      :,0].real

            threep_g0DyDz= getDatasets( threepDir, \
                                        configList, \
                                        filename, \
                                        dsetname=[ dsetname_pre \
                                                   + dsetname_insertion[ 2 ] \
                                                   + dsetname_post ] )[ :, 0, 0, \
                                                                        :, 0 ].real

            if particle == "kaon":
            
                filename_s = threep_template + ".strange.h5"

                dsetname_s_pre = "/thrp/ave{}/dt{}/strange/".format( srcNum, ts )

                threep_s_g0DxDy = getDatasets( threepDir, \
                                               configList, \
                                               filename_s, \
                                               dsetname=[ dsetname_s_pre \
                                                          + dsetname_insertion[ 0 ] \
                                                          + dsetname_post ] )[ :, 0, 0, :, 0 ].real
                threep_s_g0DxDz = getDatasets( threepDir, \
                                               configList, \
                                               filename_s, \
                                               dsetname=[ dsetname_s_pre \
                                                          + dsetname_insertion[ 1 ] \
                                                          + dsetname_post ] )[ :, 0, 0, :, 0 ].real
                threep_s_g0DyDz = getDatasets( threepDir, \
                                               configList, \
                                               filename_s, \
                                               dsetname=[ dsetname_s_pre \
                                                          + dsetname_insertion[ 2 ] \
                                                          + dsetname_post ] )[ :, 0, 0, :, 0 ].real

                threeps = np.array( [ threep_g0DxDy, threep_g0DxDz, \
                                      threep_g0DyDz, \
                                      threep_s_g0DxDy, threep_s_g0DxDz, \
                                      threep_s_g0DyDz ] )

            elif particle == "pion": 

                threeps = np.array( [ threep_g0DxDy, threep_g0DxDz, \
                                      threep_g0DyDz ] )

            else: 

                mpi_fncs.mpiPrintError( "Error (readAvgX2File): Particle " \
                    + particle + " not supported.", mpi_info )

    mpi_fncs.mpiPrint( "Read three-point functions from HDF5 files " \
                       + "in {:.3} seconds".format( time() - t0 ), \
                       mpi_info )

    threeps = np.pad( threeps, ( ( 0, 0 ), ( 0, 0 ), \
                                 ( 0, T - threeps.shape[ -1 ] ) ), \
                      'constant', \
                      constant_values=( 0.0, 0.0 ) )

    return np.asarray( threeps, order='c', dtype=float )

# Get the real part of gxDx, gyDy, gzDz, and gtDt
# three-point functions at zero-momentum

# threepDir: Head directory which contains sub-directories
# configList: List of sub-directory names
# threep_template: Filename template
# ts: Tsink
# particle: Which particle to do
# dataFormat: Which format the data files to be read are in
# dsetname (kwarg, optional): List of datasets to read. Overrides
#                             keyword

def readAvgX3File( threepDir, configList, threep_tokens, srcNum, 
                   ts, p, particle, dataFormat, T, mpi_info, **kwargs ):

    t0 = time()

    # Set filename template

    if dataFormat == "cpu":
        
        threep_template = "{0}{1}{2}{3:+}_{4:+}_{5:+}"
        threep_template = threep_template.format( threep_tokens[ 0 ], \
                                                  ts, threep_tokens[ 1 ], \
                                                  p[ 0 ], p[ 1 ], p[ 2 ] )

    else:

        error = "Error (readWrite.readAvgX2File): GPU format not supported"

        mpi_fncs.mpiPrintError( error, mpi_info )

    if particle == "nucleon":
        """
        if dataFormat == "cpu":

            filename_u_gxDx = threep_template + str( ts ) + ".up.h5"

            threep_u_gxDx = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gxDx, \
                                            "=der:gxDx:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gyDy = threep_template + str( ts ) + ".up.h5"

            threep_u_gyDy = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gyDy, \
                                            "=der:gyDy:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gzDz = threep_template + str( ts ) + ".up.h5"

            threep_u_gzDz = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gzDz, \
                                            "=der:gzDz:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_u_gtDt = threep_template + str( ts ) + ".up.h5"

            threep_u_gtDt = getDatasets( threepDir, \
                                            configList, \
                                            filename_u_gtDt, \
                                            "=der:g0D0:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gxDx = threep_template + str( ts ) + ".dn.h5"

            threep_d_gxDx = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gxDx, \
                                            "=der:gxDx:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gyDy = threep_template + str( ts ) + ".dn.h5"

            threep_d_gyDy = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gyDy, \
                                            "=der:gyDy:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gzDz = threep_template + str( ts ) + ".dn.h5"

            threep_d_gzDz = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gzDz, \
                                            "=der:gzDz:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real

            filename_d_gtDt = threep_template + str( ts ) + ".dn.h5"

            threep_d_gtDt = getDatasets( threepDir, \
                                            configList, \
                                            filename_d_gtDt, \
                                            "=der:g0D0:sym=", \
                                            "msq0000", \
                                            "arr" )[ :, 0, 0, :, 0 ].real
            
            threep_gxDx = threep_u_gxDx - threep_d_gxDx

            threep_gyDy = threep_u_gyDy - threep_d_gyDy

            threep_gzDz = threep_u_gzDz - threep_d_gzDz

            threep_gtDt = threep_u_gtDt - threep_d_gtDt

            return [ threep_gxDx, threep_gyDy, threep_gzDz, threep_gtDt ]

        else:

            print( "GPU format not supported for nucleon, yet." )

            exit()
        """
        mpi_fncs.mpiPrintError( "Error (readWrite.readAvgX2File): " \
                                + "Nucleon not supported, yet.", mpi_info )
    else: # Particle is meson
        
        if dataFormat == "gpu":
            """
            threep_gxDx = getDatasets( threepDir, \
                                          configList, \
                                          threep_template, \
                                          "tsink_" + str( ts ), \
                                          "oneD", \
                                          "dir_00", \
                                          "up", \
                                          "threep" )[ :, 0, 0, ..., 0, 1, 0 ]

            threep_gyDy = getDatasets( threepDir, \
                                          configList, \
                                          threep_template, \
                                          "tsink_" + str( ts ), \
                                          "oneD", \
                                          "dir_01", \
                                          "up", \
                                          "threep" )[ :, 0, 0, ..., 0, 2, 0 ]
    
            threep_gzDz = getDatasets( threepDir, \
                                          configList, \
                                          threep_template, \
                                          "tsink_" + str( ts ), \
                                          "oneD", \
                                          "dir_02", \
                                          "up", \
                                          "threep" )[ :, 0, 0, ..., 0, 3, 0 ]

            threep_gtDt = getDatasets( threepDir, \
                                       configList, \
                                       threep_template, \
                                       "tsink_" + str( ts ), \
                                       "oneD", \
                                       "dir_03", \
                                       "up", \
                                       "threep" )[ :, 0, 0, ..., 0, 4, 0 ]

            threep_s_gxDx = np.array( [] )
            
            threep_s_gyDy = np.array( [] )
        
            threep_s_gzDz = np.array( [] )
    
            threep_s_gtDt = np.array( [] )

            if particle == "kaon":
            
                threep_s_gxDx = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_00", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 1, 0 ]

                threep_s_gyDy = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_01", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 2, 0 ]
    
                threep_s_gzDz = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_02", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 3, 0 ]

                threep_s_gtDt = getDatasets( threepDir, \
                                                configList, \
                                                threep_template, \
                                                "tsink_" + str( ts ), \
                                                "oneD", \
                                                "dir_03", \
                                                "strange", \
                                                "threep" )[ :, 0, 0, ..., \
                                                            0, 4, 0 ]
            
                return [ threep_gxDx, threep_gyDy, \
                         threep_gzDz, threep_gtDt, \
                         threep_s_gxDx, threep_s_gyDy, \
                         threep_s_gzDz, threep_s_gtDt ]

            elif particle == "pion": 

                return [ threep_gxDx, threep_gyDy, \
                         threep_gzDz, threep_gtDt ]

            else: 

                print( "Error (readAvgXFile): Particle " \
                    + particle + " not supported." )

                exit()                
            """
            mpi_fncs.mpiPrintError( "Error (readWrite.readAvgX2File): " \
                                    + "GPU format not supported, yet.", \
                                    mpi_info )

        elif dataFormat == "cpu":

            filename = threep_template + ".up.h5"

            dsetname = "/thrp/ave{}/dt{}".format( srcNum, ts ) \
                       + "/up/der3:g0DxDyDz/msq0000/arr"

            threep = getDatasets( threepDir, \
                                  configList, \
                                  filename, \
                                  dsetname=[dsetname])[:,0,0,:,0].imag

            if particle == "kaon":
            
                filename_s = threep_template + ".strange.h5"

                dsetname_s = "/thrp/ave{}/dt{}".format( srcNum, ts ) \
                             + "/strange/der3:g0DxDyDz/msq0000/arr"

                threep_s = getDatasets( threepDir, \
                                        configList, \
                                        filename_s, \
                                        dsetname=[dsetname_s])[:,0,0,:,0].imag
                
                threeps = np.array( [ threep, threep_s ] )

            elif particle == "pion":

                threeps = np.array( [ threep ] )

            else: 

                mpi_fncs.mpiPrintError( "Error (readAvgX2File): Particle " \
                    + particle + " not supported.", mpi_info )

    mpi_fncs.mpiPrint( "Read three-point functions from HDF5 files " \
                       + "in {:.3} seconds".format( time() - t0 ), \
                       mpi_info )

    threeps = np.pad( threeps, ( ( 0, 0 ), ( 0, 0 ), \
                                 ( 0, T - threeps.shape[ -1 ] ) ), \
                      'constant', \
                      constant_values=( 0.0, 0.0 ) )

    return np.asarray( threeps, order='c', dtype=float )


def readEMFile( threepDir, configList, configNum, threep_tokens, srcNum,
                ts, momList, particle, dataFormat, insType, 
                T, mpi_info, **kwargs ):

    t0 = time()

    comm = mpi_info[ 'comm' ]
    configNum_loc_list = mpi_info[ 'configNum_loc_list' ]
    confOffset = mpi_info[ 'confOffset' ]

    if dataFormat == "gpu":            

        # Set filename template

        threep_template = threep_tokens[0]

        if insType == "local":

            iins = 4

        elif insType == "noether":

            iins = 3

        threep_loc = getDatasets( threepDir, \
                                  configList, \
                                  threep_template, \
                                  "tsink_" + str( ts ), \
                                  insType, \
                                  "up", \
                                  "threep" )[ :, 0, 0, ..., \
                                              0, iins, 0 ]

        if particle == "kaon":
            
            threep_s_loc = getDatasets( threepDir, \
                                        configList, \
                                        threep_template, \
                                        "tsink_" + str( ts ), \
                                        insType, \
                                        "strange", \
                                        "threep" )[ :, 0, 0, ..., \
                                                    0, iins, 0 ]
                
    elif dataFormat == "cpu":

        # Set filename template

        threep_template = threep_tokens[0] + str(ts) \
                          + threep_tokens[1] \
                          + fncs.signToString( momList[0] ) \
                          + str(momList[0]) + "_" \
                          + fncs.signToString( momList[1] ) \
                          + str(momList[1]) + "_" \
                          + fncs.signToString( momList[2] ) \
                          + str(momList[2])

        filename = threep_template + ".up.h5"

        dsetname_pre = "/thrp/ave{}/dt{}/up/".format( srcNum, ts )

        if insType == "local":

            dsetname_insertion = "=loc:g0="

        elif insType == "noether":

            dsetname_insertion = "=noe:g0="

        else:

            dsetname_insertion = "=noe:g0="

            print( "WARNING: insertion type not supported. " \
                   + "Will use conserved current." )

        dsetname_post = "/msq0000/arr"
            
        threep_loc = getDatasets( threepDir, \
                                  configList, \
                                  filename, \
                                  dsetname=[ dsetname_pre \
                                             + dsetname_insertion \
                                             + dsetname_post ] )[ :, 0, 0, \
                                                                  :, 0 ].real
        
        if particle == "kaon":

            filename = threep_template + ".strange.h5"

            dsetname_pre = "/thrp/ave{}/dt{}/strange/".format( srcNum, ts )

            threep_s_loc \
                = getDatasets( threepDir,
                               configList,
                               filename,
                               dsetname=[ dsetname_pre
                                          + dsetname_insertion
                                          + dsetname_post ] )[ :, 0, 0,
                                                               :, 0 ].real
            
    mpi_fncs.mpiPrint( "Read three-point functions from HDF5 files " \
                       + "in {:.3} seconds".format( time() - t0 ), \
                       mpi_info )

    threep = np.zeros( ( 1 if particle == "pion" else 2, configNum, T ), \
                       order='c', dtype=float )    

    threep_loc = np.asarray( np.pad( threep_loc, 
                                     ( ( 0, 0 ),
                                       ( 0, T - threep_loc.shape[ -1 ] ) ),
                                     'constant',
                                     constant_values=( 0.0, 0.0 ) ),
                             dtype=float, order='c' )    

    comm.Allgatherv( threep_loc, 
                     [ threep[ 0 ],
                       configNum_loc_list * np.prod( threep_loc.shape[ 1: ] ),
                       confOffset * np.prod( threep_loc.shape[ 1: ] ), 
                       MPI.DOUBLE ] )

    if particle == "kaon":

        threep_s_loc =np.asarray( np.pad( threep_s_loc, 
                                          ( ( 0, 0 ),
                                            ( 0, T-threep_s_loc.shape[-1] ) ),
                                          'constant',
                                          constant_values=( 0.0, 0.0 ) ),
                                   dtype=float, order='c' )

        comm.Allgatherv( threep_s_loc, 
                         [ threep[ 1 ], 
                           configNum_loc_list \
                           * np.prod( threep_s_loc.shape[ 1: ] ),
                           confOffset \
                           * np.prod( threep_s_loc.shape[ 1: ] ),
                           MPI.DOUBLE ] )

    return threep


def readFormFactorFile( threepDir, threep_tokens, formFactor,
                        srcNum, QsqList, QNum, ts, proj, p, T,
                        particle, dataFormat,
                        mpi_info ):

    t0 = time()

    if formFactor == "GE_GM":

        threep = readEMFormFactorFile( threepDir, threep_tokens, srcNum,
                                       QsqList, QNum, ts, proj, p, particle,
                                       T, dataFormat, mpi_info )

    elif formFactor == "A20_A22":

        mpi_fncs.mpiPrintError( "Error(readFormFactorFile): form factor " \
                           + formFactor + " not supported, yet."
                           , mpi_info )

    else:

        mpi_fncs.mpiPrintError( "Error(readFormFactorFile): form factor " \
                           + formFactor + " not supported."
                           , mpi_info )

    mpi_fncs.mpiPrint( "Read three-point functions from files " \
                       + "for tsink {} in {:.4}".format( ts,
                                                         time()
                                                         - t0 ) \
                       + " seconds.", mpi_info )

    if particle == "nucleon":

        # Calculate isovector and isoscalar

        threep_tmp = np.copy( threep_loc )

        threep[ 0 ] = 0.5 * ( threep_tmp[ 0 ] \
                              - threep_tmp[ 1 ] )
        threep[ 1 ] = 0.5 * ( threep_tmp[ 0 ] \
                              + threep_tmp[ 1 ] )

    return threep


def readEMFF_cpu( threepDir, threep_template, srcNum,
                  Qsq, ts, proj, particle, flav, T,
                  **kwargs ):

    configList = mpi_info[ 'configList' ]

    QsqNum = len( Qsq )

    insertionCurrent = [ "=noe:g0=" , \
                         "=noe:gx=" , \
                         "=noe:gy=" , \
                         "=noe:gz=" ]
                         
    insertionNum = len( insertionCurrent )

    # Set data set names

    dsetname = [ "" for qc in range( QsqNum * insertionNum ) ]
                
    # Loop over Qsq
    for qsq, iqsq in zip( Qsq, range( QsqNum ) ):
        # Loop over insertion current
        for c, ic in zip( insertionCurrent, range( insertionNum ) ):
            
            if particle == "nucleon":

                template = "/thrp/ave{}/P{}/dt{}/{}/{}/msq{:.4}/arr"
                    
                dsetname[ iqsq * QsqNum + ic ] = template.format( srcNum, \
                                                                  proj, \
                                                                  ts, \
                                                                  flav, \
                                                                  c, qsq )

            else:

                template = "/thrp/ave{}/dt{}/{}/{}/msq{:.4}/arr"
                    
                dsetname[ iqsq * QsqNum + ic ] = template.format( srcNum, \
                                                                  ts, \
                                                                  flav, \
                                                                  c, qsq )

        # End loop over insertion current
    # End loop over Qsq

    # Read three-point files
    # threep[ conf, Q*curr, t ]

    threep = getDatasets( threepDir,
                          configList,
                          threep_template,
                          dsetname=dsetname )[:,0,:,:]

    # Reshape threep[ conf, Qsq*curr, t ] 
    # -> threep[ conf, Q, curr, t ]

    threep = threep.reshape( threep.shape[ 0 ], QsqNum,
                             insertionNum, threep.shape[ -1 ] )
                        
    return threep

    
def readEMFF_gpu( threepDir, threep_template,
                  QNum, ts, flav, dataFormat, T, 
                  mpi_info, **kwargs ):

    configList = mpi_info[ 'configList_loc' ]
    configNum = len( configList )

    dset_keywords = [ "tsink_{}".format( ts ),
                      flav,
                      "noether" ]

    # threep_tmp[ conf, t, Q, curr, re/im ]
    threep_tmp = getDatasets( threepDir, configList,
                              threep_template,
                              *dset_keywords )[ :, 0, 0, :, :, :, : ]

    # Change current order from x, y, z, t -> t, x, y, z
    # and make complex
    # threep[ conf, t, Q, curr ]

    threep = np.zeros( threep_tmp.shape[ :-1 ], dtype=complex )

    threep[ ..., 0 ] = threep_tmp[ ..., 3, 0 ] \
                       + 1j * threep_tmp[ ..., 3, 1 ]

    threep[ ..., 1: ] = threep_tmp[ ..., :3, 0 ] \
                        + 1j *threep_tmp[ ..., :3, 1 ]

    # threep[ conf, t, Q, curr ] -> threep[ conf, Q, curr, t ]
    threep = np.moveaxis( threep, 1, 3 )

    return threep


def readEMFF_ASCII( threepDir, threep_template,
                    QNum, insertionNum, T, mpi_info, **kwargs ):

    configList = mpi_info[ 'configList' ]

    # threep[ conf, QNum*t*curr ]
    
    threep = getTxtData( threepDir, configList,
                         threep_template, dtype=float )[ ..., 4:6 ]

    if "comm" in kwargs:

            mpi_fncs.mpiPrint( threep, kwargs["comm"].Get_rank() )

    threep = threep[ ..., 0 ] + threep[ ..., 1 ] * 1j

    T = threep.shape[ -1 ] // QNum // insertionNum

    if "comm" in kwargs:

            mpi_fncs.mpiPrint( threep, kwargs["comm"].Get_rank() )

    # Reshape threep[ conf, Q*t*curr ] 
    # -> threep[ conf, Q, t, curr ]
    
    threep = threep.reshape( threep.shape[ :-1 ] + \
                             ( QNum, T, insertionNum ) )

    # threep[ conf, Q, t, curr ] 
    # -> threep[ conf, Q, curr, t ]

    threep = np.moveaxis( threep, -1, -2 )

    return threep


def readEMFormFactorFile( threepDir, threep_tokens, srcNum,
                          Qsq, QNum, ts, projector, p, particle, T,
                          dataFormat, mpi_info, **kwargs ):

    comm = mpi_info[ 'comm' ]
    configNum = mpi_info[ 'configNum' ]
    configNum_loc = mpi_info[ 'configNum_loc' ]
    configNum_loc_list = mpi_info[ 'configNum_loc_list' ]
    confOffset = mpi_info[ 'confOffset' ]

    projectorNum = len( projector )

    flavor, flavorNum = fncs.setFlavorStrings( particle, dataFormat )

    currNum = fncs.setCurrentNumber( "GE_GM", mpi_info )

    threep_loc = np.zeros( ( configNum_loc, flavorNum,
                             projectorNum, QNum, currNum, T ),
                           dtype=complex )

    # Loop over flavor
    for flav, iflav in zip( flavor, range( flavorNum ) ):
        # Loop over projector
        for proj, iproj in zip( projector, range( projectorNum ) ):

            # Set filename template
    
            if dataFormat == "cpu":
                
                template = "{0}{1}{2}{3:+}_{4:+}_{5:+}.{6}.h5"
    
                threep_template = template.format( threep_tokens[0],
                                                   ts,
                                                   threep_tokens[1],
                                                   p[0], p[1], p[2],
                                                   flav )

                threep_loc[ :, iflav, iproj ] = readEMFF_cpu( threepDir,
                                                              threep_template,
                                                              srcNum, Qsq, ts, proj,
                                                              particle, flav, T,
                                                              **kwargs )
                
            elif dataFormat == "gpu":

                template = "{0}{1}{2}"

                threep_template = template.format( threep_tokens[0],
                                                   particle,
                                                   threep_tokens[1] )

                # threep_tmp[ conf, Q, curr, t ]

                threep_tmp = readEMFF_gpu( threepDir,
                                           threep_template,
                                           QNum, ts, flav,
                                           dataFormat, T,
                                           mpi_info,
                                           **kwargs )

                threep_loc[ :, iflav, iproj, ..., :threep_tmp.shape[ -1 ] ] \
                    = threep_tmp

            elif dataFormat == "ASCII":

                template = "{0}{1}{2}{3}{4}{5}"

                threep_template = template.format( threep_tokens[0], proj,
                                                   threep_tokens[1], ts,
                                                   threep_tokens[2],
                                                   flav )

                threep_loc[ :, iflav, iproj ] = readEMFF_ASCII( threepDir,
                                                             threep_template,
                                                             QNum, 4, **kwargs )

        # End loop over projector
    # End loop over flavor

    # Get the projector and insertion combinations we want
    # threep_loc[ flav, proj, conf, Q, curr, t ]
    # -> threep_loc[ flav, conf, Q, ratio, t ]

    if particle == "nucleon":

        # threep_loc[ conf, flav, proj, Q, curr, t ]
        # -> threep_loc[ conf, flav, Q, ratio, t ]

        # ratio   Projector Insertion
        # 0       P0 gt
        # 1       P0 gx
        # 2       P0 gy
        # 3       P0 gz
        # 4       P4 gy
        # 5       P4 gz
        # 6       P5 gx
        # 7       P5 gz
        # 8       P6 gx
        # 9       P6 gy

        threep_loc = np.stack ( [ threep_loc[ :, :, 0, :, 0, : ].real,
                                  threep_loc[ :, :, 0, :, 1, : ].imag,
                                  threep_loc[ :, :, 0, :, 2, : ].imag,
                                  threep_loc[ :, :, 0, :, 3, : ].imag,
                                  threep_loc[ :, :, 1, :, 2, : ].real,
                                  threep_loc[ :, :, 1, :, 3, : ].real,
                                  threep_loc[ :, :, 2, :, 1, : ].real,
                                  threep_loc[ :, :, 2, :, 3, : ].real,
                                  threep_loc[ :, :, 3, :, 1, : ].real,
                                  threep_loc[ :, :, 3, :, 2, : ].real ],
                                axis=3 )
        
    else:

        # ratio   Insertion
        # 0       gt
        # 1       gx
        # 2       gy
        # 3       gz

        threep_loc = np.stack ( [ threep_loc[ :, :, 0, :, 0, : ].real,
                                  threep_loc[ :, :, 0, :, 1, : ].imag,
                                  threep_loc[ :, :, 0, :, 2, : ].imag,
                                  threep_loc[ :, :, 0, :, 3, : ].imag ],
                                axis=3 )

    threep = np.zeros( ( configNum, ) \
                       + threep_loc.shape[ 1: ] )

    comm.Allgatherv( threep_loc,
                     [ threep,
                       configNum_loc_list \
                       * np.prod( threep_loc.shape[ 1: ] ),
                       confOffset \
                       * np.prod( threep_loc.shape[ 1: ] ),
                       MPI.DOUBLE ] )

    return threep


########################
# ASCII read functions #
########################


def getTxtData( configDir, configList, fn_template, **kwargs ):

    configNum = len( configList )

    data = fncs.initEmptyList( configNum, 1 )

    # Loop over config indices
    for c in range( configNum ):
        
        filename = configDir + fn_template.replace( "*", configList[ c ] )

        # Get data

        data[ c ] = readTxtFile( filename, **kwargs )

    # End loop over configs

    return np.array( data )


def readTxtFile( filename, **kwargs ):

    with open( filename, "r" ) as txtFile:

        lines = txtFile.readlines()

        lineNum = len( lines )

        columnNum = len( lines[0].split() )

        # Go back to beginning of file
        
        txtFile.seek( 0 )

        data = np.array( txtFile.read().split(), \
                         **kwargs ).reshape( lineNum, \
                                             columnNum )

    return data


# Reads an ASCII file with two columns where the data of 
# interest is in the last column. Lines should repeat 
# over d1 and then d0. Data is stored in an array with 
# shape ( d0, d1 ).

# filename: Name of data file to be read
# d0: Last dimension data is repeated over, 
#     to be first dimension in output
# d1: First dimension data is repeated over,
#     to be last dimension in output

def readDataFile( filename, d0, d1 ):

    with open( filename, "r" ) as file:

        data = np.array( file.read().split(), dtype=float )

    data = data.reshape( d0, d1, 2  )

    return data[ ..., -1 ]


# Reads the Nth column of an ASCII data file.

# filename: Name of data file to be read
# N: Column number to be read (counting starts at 0)

def readNthDataCol( filename, N ):

    data = []

    with open( filename, "r" ) as file:

        for line in file:

            if line.split():

                data.append( line.split() )

    data = np.array( data, dtype=float )

    return data[ ..., N ]

"""
# Reads and ASCII file of (most often) form factor data 
# with three columns where the data of interest is in 
# the last column. Lines should repeat over d2, then d1, 
# and lastly d0. Data is stored in an array with shape 
# ( d0, d1, d2 ).

# filename: Name of data file to be read
# d0: Last dimension data is repeated over, 
#     to be first dimension in output
# d1: Second dimension data is repeated over
#     and in output
# d2: First dimension data is repeated over,
#     to be last dimension in output

def readFormFactorFile( filename, d0, d1, d2 ):

    with open( filename, "r" ) as file:

        data = np.array( file.read().split(), dtype=float )

    data = data.reshape( d0, d1, d2, 3  )

    # Return data in the last column

    return data[ ..., -1 ]
"""

########################################
# Determine values from file functions #
########################################


# Determines the number of timesteps and configurations
# for file whose first column is time and which repeats
# configurations after timesteps

# filename: Name of file whose timestep and configuration
#           number will be determined

def detTimestepAndConfigNum( filename ):

    t_last = -1

    timestepNum = 0

    timestepNum_last = -1

    configNum = 0

    # Open file
    with open( filename, "r" ) as file:
        # Loop over lines
        for line in file:

            # Get first column

            t = int( line.split()[ 0 ] )

            # If next timestep

            if t == ( t_last + 1 ):

                timestepNum += 1

                t_last = t

            # Else if timesteps have started over

            elif t == 0:

                # If this is not first time counting timestepNum

                if timestepNum_last >= 0:

                    assert timestepNum == timestepNum_last, \
                        "Error (detTimestepAndConfigNum): " \
                        + "Number of timesteps not" \
                        + " consistent across configurations"
                    
                timestepNum_last = timestepNum

                timestepNum = 1

                configNum += 1

                t_last = t

            # Else unsupported behaviour

            else:

                print( "Error (detTimestepAndConfigNum): " \
                       + "Timestep in 1st column " \
                    + "does not behave as expected" )

                return -1

            # End if
        # End loop over lines
    # Close file

    assert timestepNum == timestepNum_last, \
        "Error (detTimestepAndConfigNum): " \
        + "Number of timesteps not" \
        + " consistent across configurations"
                    
    configNum += 1

    return timestepNum, configNum


# Determines the number of Q^2's, configurations, and timesteps
# for file whose first column is time, second column is Q^2,
# and which repeats Q^2  after timesteps and configurations
# after Q^2

# filename: Name of file whose Q^2, timestep, and configuration
#           number will be determined

def detQsqConfigNumAndTimestepNum( filename ):

    t_last = -1

    q_last = 0
    
    # We can set the 1st Qsq to zero because we will
    # check that it is equal to q_last

    Qsq = [ 0 ] 

    configNum = 0

    configNum_last = -1

    timestepNum = 0

    timestepNum_last = -1

    with open( filename, "r" ) as file:

        for line in file:

            t = int( line.split()[ 0 ] )

            q = int( line.split()[ 1 ] )

            # If next timestep and Q^2 is the same as last

            if t == ( t_last + 1 ) and q == q_last:

                timestepNum += 1

            # Else if timesteps have started over

            elif t == 0:

                # If this is not the first time counting timestep number

                if timestepNum_last >= 0:

                    assert timestepNum == timestepNum_last, \
                        "Error (detQsqConfigNumAndTimestepNum): " \
                        + "Number of timesteps is not " \
                        + "consistent across configurations"
                    
                timestepNum_last = timestepNum

                timestepNum = 1

                configNum += 1

                # If next Q^2

                if q > q_last:

                    # If this in not the first time counting Q^2 number

                    if configNum_last >= 0:

                        assert configNum == configNum_last, \
                            "Error (detQsqConfigNumAndTimestepNum): "\
                            + "Number of configurations is not " \
                            + "consistent across Qsq's"

                    configNum_last = configNum

                    configNum = 0

                    Qsq.append( q )

            # Else unsupported behaviour

            else:

                print( "Error (detTimestepAndConfigNum): " \
                       + "Timestep in 1st column " \
                       + "does not behave as expected" )

                return -1

            t_last = t

            q_last = q

    assert timestepNum == timestepNum_last, \
        "Error (detTimestepAndConfigNum): Number of timesteps not" \
        + " consistent across configurations"
                    
    configNum += 1

    assert configNum == configNum_last, \
        "Error (detQsqConfigNumAndTimestepNum): Number of " \
        + "configurations is not consistent across Qsq's"

    return np.array( Qsq ), configNum, timestepNum


###################
# Write functions #
###################


# Writes an ASCII file with two columns and two repeating dimensions.
# The first column is the first repeating dimension and the second is
# the data.

# filename: Name of file to be written
# data: 2-D array of data to be written in the second column

def writeDataFile( filename, data ):

    if data.ndim != 2:

        print( "Error (writeDataFile): Data array does not " \
               + "have two dimensions" )

        return -1

    with open( filename, "w" ) as output:

        for d0 in range( len( data ) ):

            for d1 in range( len( data[ d0 ] ) ):
                
                output.write( "{:<5d}{:<20.15}\n".format( d1, \
                                                          data[ d0, d1 ] ) )

    print( "Wrote " + filename )

# Write an ASCII file with three columns. The first column is row number,
# the second column is a set of data, and the third column is another 
# set of data, often the error associated with the first set of data.

# filename: Name of file to be written
# data: 1-D array of data to be written in the second column
# error: 1-D array of data to be written in the third column

def writeAvgDataFile( filename, data, error ):

    if data.ndim != 1:

        print( "Error (writeAvgDataFile): Data array has more " \
               + "than one dimension" )

        return -1

    if data.shape != error.shape or len( data ) != len( error ):

        print( "Error (writeAvgDataFile): Error array's length and " \
               + "shape does not match data array's" )
        
        return -1

    with open( filename, "w" ) as output:

        for d0 in range( len( data ) ):

            output.write( "{:<5d}{:<25.15}{:<25.15}\n".format(d0, \
                                                              data[ d0 ], \
                                                              error[ d0 ]) )

    print( "Wrote " + filename )


# Same as writeAvgDataFile except the first column is a set of given numbers
# instead of simply the row number.

# filename: Name of file to be written
# x: 1-D array of data to be written in the first column
# y: 1-D array of data to be written in the second column
# error: 1-D array of data to be written in the third column

def writeAvgDataFile_wX( filename, x, y, error ):

    assert y.ndim == 1, "Error (writeAvgDataFile_wX): Data array has more " \
        + "than one dimension"

    assert y.shape == error. shape and len( y ) == len( error ), \
        "Error (writeAvgDataFile_wX): Error array's length and " \
        + "shape does not match data array's" 

    assert len( y ) == len( x ), \
        "Error (writeAvgDataFile_wX): x array's length and " \
        + "shape does not match data array's" 

    with open( filename, "w" ) as output:

        if x.ndim == 2:

            for ix, iy, ierr in zip( x, y, error ):

                x_str = " ".join( "{:>2}".format( xx ) for xx in ix )

                output.write( "{:<10}{:<20.10f}{:.10f}\n".format( x_str,
                                                                iy,
                                                                ierr) )
            
        elif x.dtype == int:
            
            for ix, iy, ierr in zip( x, y, error ):

                output.write( "{:<20d}{:<20.10f}{:.10f}\n".format( ix,
                                                                   iy,
                                                                   ierr) )

        elif x.dtype == '<U6':

            for ix, iy, ierr in zip( x, y, error ):

                output.write( "{:<20}{:<20.10f}{:.10f}\n".format( ix,
                                                                  iy,
                                                                  ierr) )            

        else: # Default: treat x as float

            for ix, iy, ierr in zip( x, y, error ):

                output.write( "{:<20.10f}{:<20.10f}{:.10f}\n".format( ix,
                                                                      iy,
                                                                      ierr) )

        

    print( "Wrote " + filename )


# Write an ASCII file with three columns and three repeating dimensions. 
# The first column is the first repeating dimension which increases by one,
# the second column is the second repeating dimension which is given,
# and the third column is a set of data.

# filename: Name of file to be written
# Qsq: 1-D array of data to be written repeatedly in the second column
# data: 3-D array of data to be written in the third column

def writeFormFactorFile( filename, Qsq, data ):

    assert data.ndim == 3, "Error (writeFormFactorFile): " \
        + "Data array does not have three dimensions"

    with open( filename, "w" ) as output:

        for q in range( data.shape[ 0 ] ):

            for b in range( data.shape[ 1 ] ):
                
                for t in range( data.shape[ 2 ] ):

                    output.write( str( t ).ljust(20) \
                                  + str( Qsq[ q ] ).ljust(20) \
                                  + str( data[ q, b, t ] ) + "\n" )

    print( "Wrote " + filename )


# Write an ASCII file with four columns and three repeating dimensions. 
# The first column is the first repeating dimension which increases by one,
# the second column is the second repeating dimension which is given,
# and the third and fourth columns are a set of data pairs.

# filename: Name of file to be written
# data: 3-D array of data pairs to be written in the third and fourth columns
# Qsq: 1-D array of data to be written repeatedly in the second column

def writeSVDOutputFile( filename, data, Qsq ):

    with open( filename, "w" ) as output:

        for q in range( len( data ) ):

            for r in range( data[ q ].shape[ 0 ] ):

                output.write("{:<10}{:<10}{:<20.10}{:<.10}\n".format(r, \
                                                                     Qsq[q], \
                                                                     data[q][r,0], \
                                                                     data[q][r,1]))

    print( "Wrote " + filename )


# Write an ASCII file with four columns and 2 repeating dimensions. 
# The first column is the first repeating dimension which increases by one,
# the second column is the second repeating dimension which is given,
# and the third column is a set of data, and the fourth column is another
# set of data, often the error associated with the other set.

# filename: Name of file to be written
# Qsq: 1-D array of data to be written repeatedly in the second column
# data: 2-D array of data to be written in the third column
# error: 2-D array of data to be written in the fourth column

def writeAvgFormFactorFile( filename, Qsq, data, error ):

    assert data.ndim == 2, "Error (writeAvgFormFactorFile): " \
        + "Data array does not have two dimensions"

    assert data.shape == error.shape, "Error (writeAvgFormFactorFile): " \
        + "Error array's shape does not match data array's"
        
    with open( filename, "w" ) as output:

        for q in range( data.shape[ 0 ] ):

            for t in range( data.shape[ 1 ] ):

                output.write( str( t ).ljust(5) 
                              + str( Qsq[ q ] ).ljust(10) 
                              + str( data[ q, t ] ).ljust(20) 
                              + str( error[ q, t ] ) + "\n" )

    print( "Wrote " + filename )


# Write one line of data with four values. Most often used for constant fit 
# values, their associated error, and the start and ending values of the fit 
# range.

# filename: Name of file to be written
# fit: First number to be written
# err: Second number to be written
# fitStart: number to be written
# fitEnd: number to be written

def writeFitDataFile( filename, fit, err, fitStart, fitEnd ):

    with open( filename, "w" ) as output:

        output.write( str( fit ).ljust( 20 ) 
                      + str( err ).ljust( 20 ) 
                      + str( int( fitStart ) ).ljust( 5 ) 
                      + str( int( fitEnd ) ) + "\n" )

    print( "Wrote " + filename )


# Write the fit parameters for a two-state fit of two- and three-point 
# functions

# filename: Name of file to be written
# params: List of seven fit parameters
# params_err: Error associated with each fit parameter

def writeTSFParamsFile( filename, params, params_err ):

    assert len( params ) == 7, "Error (writeTwoStateFitParams): " \
        + "number of fit parameters should be 7."

    assert len( params ) == len( params_err ), \
        "Error (writeTwoStateFitParams): " \
        + "number of parameters and number of parameter errors do not match."

    with open( filename, "w" ) as output:

        # A00
        output.write( "A00".ljust( 5 ) 
                      + str( params[ 0 ] ).ljust( 20 ) 
                      + str( params_err[ 0 ] ) + "\n" )

        # A01
        output.write( "A01".ljust( 5 ) 
                      + str( params[ 1 ] ).ljust( 20 ) 
                      + str( params_err[ 1 ] ) + "\n" )

        # A11
        output.write( "A11".ljust( 5 ) 
                      + str( params[ 2 ] ).ljust( 20 ) 
                      + str( params_err[ 2 ] ) + "\n" )

        # c0
        output.write( "c0".ljust( 5 ) 
                      + str( params[ 3 ] ).ljust( 20 ) 
                      + str( params_err[ 3 ] ) + "\n" )

        # c1
        output.write( "c1".ljust( 5 ) 
                      + str( params[ 4 ] ).ljust( 20 ) 
                      + str( params_err[ 4 ] ) + "\n" )

        # E0
        output.write( "E0".ljust( 5 ) 
                      + str( params[ 5 ] ).ljust( 20 ) 
                      + str( params_err[ 5 ] ) + "\n" )

        # E1
        output.write( "E1".ljust( 5 ) 
                      + str( params[ 6 ] ).ljust( 20 ) 
                      + str( params_err[ 6 ] ) + "\n" )

    print( "Wrote " + filename )


# Write the fit parameters for a two-state fit of two-point functions

# filename: Name of file to be written
# params: List of four fit parameters
# params_err: Error associated with each fit parameter

def writeTSFParamsFile_twop( filename, params, params_err ):

    assert len( params ) == 4, "Error (writeTwoStateFitParams): " \
        + "number of fit parameters should be 4."

    assert len( params ) == len( params_err ), \
        "Error (writeTwoStateFitParams): " \
        + "number of parameters and number of parameter errors do not match."

    with open( filename, "w" ) as output:

        # c0
        output.write( "c0".ljust( 5 ) 
                      + str( params[ 0 ] ).ljust( 20 ) 
                      + str( params_err[ 0 ] ) + "\n" )

        # c1
        output.write( "c1".ljust( 5 ) 
                      + str( params[ 1 ] ).ljust( 20 ) 
                      + str( params_err[ 1 ] ) + "\n" )

        # E0
        output.write( "E0".ljust( 5 ) 
                      + str( params[ 2 ] ).ljust( 20 ) 
                      + str( params_err[ 2 ] ) + "\n" )

        # E1
        output.write( "E1".ljust( 5 ) 
                      + str( params[ 3 ] ).ljust( 20 ) 
                      + str( params_err[ 3 ] ) + "\n" )

    print( "Wrote " + filename )

