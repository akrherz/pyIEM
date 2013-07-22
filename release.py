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

#os.unlink("MANIFEST")

# Step 1
config = ConfigParser.ConfigParser()
config.read('setup.cfg')
nextval = int(config.get('bdist_rpm', 'release')) + 1
config.set('bdist_rpm', 'release', nextval)
config.write( open('setup.cfg', 'w'))

# Step 2
subprocess.call("rm -f dist/*", shell=True)

# Step 3
subprocess.call("python setup.py bdist_rpm", shell=True)

# Step 4
subprocess.call("titan dist/*noarch.rpm", shell=True)
