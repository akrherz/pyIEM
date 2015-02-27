'''
 Automate the release process of this code base
 1) Increment build release
 2) Clean dist area
 3) Build RPM
 4) Publish RPM to local RHN satellite
'''
import ConfigParser
import subprocess
import os
import sys

rhel = sys.argv[1]
if rhel not in ['rhel6', 'rhel7']:
    print 'argv[1] must be either rhel6 or rhel7'
    sys.exit()

# Step 0, remove MANIFEST
if os.path.isfile("MANIFEST"):
    os.unlink("MANIFEST")

# Step 1
config = ConfigParser.ConfigParser()
config.read('setup.cfg')
nextval = int(config.get('bdist_rpm', 'release')) + 1
config.set('bdist_rpm', 'release', nextval)
config.write(open('setup.cfg', 'w'))

# Step 2
subprocess.call("rm -f dist/*", shell=True)

# Step 3
subprocess.call("""python setup.py bdist_rpm --release=%s.%s""" % (
                        nextval, rhel), shell=True)

# Step 4
subprocess.call("titan dist/*noarch.rpm", shell=True)
