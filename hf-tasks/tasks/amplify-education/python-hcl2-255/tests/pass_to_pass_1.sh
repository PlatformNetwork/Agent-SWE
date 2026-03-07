#!/bin/bash
# This test must PASS on base commit AND after fix
python -m nose2 -s test/unit -v test_dict_transformer
