#ifndef READWRITE_H
#define READWRITE_H
#endif

#include <iostream>
#include <vector>
#include "hdf5.h"

#define READ_DIM_NUM 10

using std::vector;

namespace lQCD_jk {

  typedef struct readInfo {

    int dimNum;
    int subDim[READ_DIM_NUM];
    
    int count[READ_DIM_NUM];
    int offset[READ_DIM_NUM];
    int stride[READ_DIM_NUM];
    int block[READ_DIM_NUM];
    
  } readInfo;

}

void readTwopMesons_0mom(std::vector< std::vector<double> > *data, char *file, char *dataset, lQCD_jk::readInfo info);