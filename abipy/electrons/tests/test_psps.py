from __future__ import division, print_function, unicode_literals

import numpy as np
import abipy.data as abidata
import abipy.core

from abipy.core.testing import *
from abipy.electrons.psps import PspsFile

from abipy.core.testing import has_matplotlib


class PspsFileTestCase(AbipyTest):

    def test_psps_nc_silicon(self):
        """Very preliminary test for PSPS.nc file with Ga.oncvpsp"""
        pseudo = abidata.pseudo("Ga.oncvpsp")

        with pseudo.open_pspsfile(ecut=10) as psps:
            print(psps)
            r = psps.reader
            assert r.usepaw == 0 and r.ntypat == 1

            if has_matplotlib():
                psps.plot(what="all", show=False)
                psps.compare(psps, show=False)



if __name__ == "__main__":
    import unittest
    unittest.main()
