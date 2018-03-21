#include <iostream>
#include "readWrite.h"

using namespace lQCD_jk;
using std::cout;
using std::endl;

int main (void) {

  char *file = "/home/tuf47161/work/L16T32/twop/1505-MG/twop.1505_mesons_Qsq64_SS.00.08.09.04.h5";
  char *dataset = "/conf_1505/sx00sy08sz09st04/g1/twop_meson_1";

  readInfo rInfo;

  rInfo.dimNum = 3;

  rInfo.subDim[0] = 32;
  rInfo.subDim[1] = 1;
  rInfo.subDim[2] = 2;

  rInfo.count[0] = 32;
  rInfo.count[1] = 1;
  rInfo.count[2] = 2;

  rInfo.offset[0] = 0;
  rInfo.offset[1] = 0;
  rInfo.offset[2] = 0;

  rInfo.stride[0] = 1;
  rInfo.stride[1] = 1;
  rInfo.stride[2] = 1;

  rInfo.block[0] = 1;
  rInfo.block[1] = 1;
  rInfo.block[2] = 1;

  vector< vector<double> > data(rInfo.subDim[0]);

  readTwopMesons_0mom(&data, file, dataset, rInfo);

  for(int i=0; i<data.size(); i++)
    cout << data.at(i).at(0) << ", " << data.at(i).at(1) << endl;

  return 0;
}
