# coding: utf-8
import sys, os, re, argparse, glob
#
import config
from lib import util

#
#                                                      (R)
#                      ---                  ---
#                    #@@@@@@              &@@@@@@
#                    @@@@@@@@     .@      @@@@@@@@
#          -----      @@@@@@    @@@@@@,   @@@@@@@      -----
#       &@@@@@@@@@@@    @@@   &@@@@@@@@@.  @@@@   .@@@@@@@@@@@#
#           @@@@@@@@@@@   @  @@@@@@@@@@@@@  @   @@@@@@@@@@@
#             \@@@@@@@@@@   @@@@@@@@@@@@@@@   @@@@@@@@@@
#               @@@@@@@@@   @@@@@@@@@@@@@@@  &@@@@@@@@
#                 @@@@@@@(  @@@@@@@@@@@@@@@  @@@@@@@@
#                  @@@@@@(  @@@@@@@@@@@@@@,  @@@@@@@
#                  .@@@@@,   @@@@@@@@@@@@@   @@@@@@
#                   @@@@@@  *@@@@@@@@@@@@@   @@@@@@
#                   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@.
#                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
#                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@
#                     .@@@@@@@@@@@@@@@@@@@@@@@@@
#                       .@@@@@@@@@@@@@@@@@@@@@
#                            jankvetina.cz
#                               -------
#
# Copyright (c) Jan Kvetina, 2024
# https://github.com/jkvetina/ADT
#

class Deploy(config.Config):

    # show the list of undeployed patches
    # identify patch folder
    # verify that previous patches were deployed -> show warning/confirm
    # it would be supercool to check if (and which) files overlaps !!!
    # verify if requested patch was deployed to that env or not, ignore if -force = Y
    # stop if other deploy is in progress - HOW ??? commit to branch ?
    # lock env for simultaneous patching
    # connect to target env, to each schema
    # run the target script(s) and spool the logs
    # check TEMPLATE for pre/post deploy folders/files
    # recompile invalid objects
    # unlock env
    # store the results - rename the log files ?
    # requested deployed objects for quick compare
    # check APEX hashes for APEX files ?
    # store the record of deployment: patch, env name, date, author (email)
    # commit the logs automatically ? which branch ?
    # create tag in repo ?

    def __init__(self, parser):
        super().__init__(parser)

        # process arguments and reinitiate config
        self.patch_code         = self.args.patch
        self.patch_seq          = self.args.seq or ''
        self.info.branch        = self.args.branch or self.info.branch or self.repo.active_branch
        #
        self.init_config()
        self.deploy_patch()



    def deploy_patch(self):
        pass



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument('-debug',       help = 'Turn on the debug/verbose mode',    default = False, nargs = '?', const = True)
    parser.add_argument('-key',         help = 'Key or key location to encypt passwords')
    parser.add_argument('-schema',      help = 'Schema/connection name')
    #
    parser.add_argument('-patch',       help = 'Patch code (name for the patch files)')
    parser.add_argument('-seq',         help = 'Sequence in patch folder, {$PATCH_SEQ}')
    parser.add_argument('-target',      help = 'Target environment')
    parser.add_argument('-force',       help = 'Force deployment',                          default = False, nargs = '?', const = True)
    #
    Deploy(parser)

