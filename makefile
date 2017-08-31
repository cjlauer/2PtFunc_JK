CXX = g++

all : effMass.exe gA.exe gT.exe avgX.exe scalarFF.exe fitValue.exe fitFormFactor.exe

jk.o: jk.cpp ; $(CXX) -c -I. jk.cpp

fitting.o: fitting.cpp ; $(CXX) -c -I. fitting.cpp

physQuants.o: physQuants.cpp ; $(CXX) -c -I. physQuants.cpp

effMass.o: effMass.cpp ; $(CXX) -c -I. effMass.cpp

effMass.exe: effMass.o jk.o physQuants.o ; $(CXX) -o effMass.exe \
	effMass.o jk.o physQuants.o\

gA.o: gA.cpp ; $(CXX) -c -I. gA.cpp

gA.exe: gA.o jk.o fitting.o ; $(CXX) -o gA.exe \
	gA.o jk.o fitting.o\

gT.o: gT.cpp ; $(CXX) -c -I. gT.cpp

gT.exe: gT.o jk.o fitting.o ; $(CXX) -o gT.exe \
	gT.o jk.o fitting.o\

avgX.o: avgX.cpp ; $(CXX) -c -I. avgX.cpp

avgX.exe: avgX.o jk.o fitting.o ; $(CXX) -o avgX.exe \
	avgX.o jk.o fitting.o\

scalarFF.o: scalarFF.cpp ; $(CXX) -c -I. scalarFF.cpp

scalarFF.exe: scalarFF.o jk.o fitting.o physQuants.o ; $(CXX) -o scalarFF.exe \
	scalarFF.o jk.o fitting.o physQuants.o\

fitValue.o: fitValue.cpp ; $(CXX) -c -I. fitValue.cpp

fitValue.exe: fitValue.o jk.o fitting.o ; $(CXX) -o fitValue.exe \
	fitValue.o jk.o fitting.o\

fitFormFactor.exe: fitFormFactor.o jk.o fitting.o ; $(CXX) -o fitFormFactor.exe \
	fitFormFactor.o jk.o fitting.o\

clean: 
	rm -f *.o
	rm -f *.exe
	rm -f *~

