#!/usr/bin/env python3

import subprocess
import re
import sys
import time

# Config section
# 
listWidth = 700
# User master that will be set when erasing
masterUser = 'u'
# And the security password
securityPassword = 'p'
# Minimum progress bar update interval
minProgBarUpdateInterval = 5
# Time to wait for hdparm to erase before assuming it's an error (in secs)
hdparmTimeout = 10.0

# Dry run: do not effectively erase the disk
dryRun = False

# TODO: check if hdparm is available and display an error if it's not

def ListDisks():
	# List connected devices
	# Decode converts to strings
	blockDevices = subprocess.run( ['lsblk', '-d'], stdout=subprocess.PIPE, universal_newlines = True ).stdout.splitlines()

	diskTag = 'disk'

	# Disks
	disks = {}

	for blockDev in blockDevices:

		if not diskTag in blockDev:
			continue
		print(blockDev )

		# Extract device name
		##match = re.search( r'^(\w+)\t', device )
		match = re.search( r'^(\w+)\s', blockDev )
		device = match.group(1)
		print( device )

		#disks.append( device )
		diskStatus = GetDiskInfo( device )
		# If the disk is not valid
		if diskStatus == False:
			# Don't add it to the dict
			continue

		disks[ device ] = diskStatus
	return disks


def GetDiskInfo( disk ):
	diskInfo = dict()

	# Some default values
	diskInfo['securityEnabled'] = False
	# If there is no security section, this drive is not valid
	securitySection = False

	# Call hdparm
	hdparmOutput = subprocess.run( ['hdparm', '-I', '/dev/{}'.format( disk )], stdout=subprocess.PIPE, universal_newlines = True ).stdout.splitlines()
	#hdparmOutput = subprocess.check_output( ['hdparm', '-I','/dev/sda'] ).decode().splitlines()
	#print( hdparmOutput )
	for line in hdparmOutput:
		# Security section
		if 'Security:' in line:
			securitySection = True
		# Model number
		if 'Model Number' in line:
			print( line )
			match = re.search( r'^\s*Model Number:\s*(.+?)\s*$', line )
			diskInfo['model'] = match.group(1)
		# Check if the disk is frozen or not
		if 'frozen' in line:
			match = re.search( r'^\s*not\s+(frozen)', line )
			# The disk is frozen if the line does not say "not frozen"
			diskInfo['frozen'] = ( match == None )
		# Check if it's locked
		if 'locked' in line:
			match = re.search( r'^\s*not\s+(locked)', line )
			diskInfo['locked'] = ( match == None )


		# Enhanced security erase
		if 'enhanced erase' in line:
			match = re.search( r'^\s*supported:\s+enhanced erase', line )
			diskInfo['enhancedErase'] = ( match != None )
		# Secure erase time
		if 'ERASE UNIT' in line:
			match = re.search( r'^\s*(\d+)min for SECURITY ERASE UNIT', line )
			diskInfo['erase'] = ( match != None )
			if match :
				diskInfo['eraseTime'] = match.group(1)
			match = re.search( r'\s*(\d+)min for ENHANCED SECURITY ERASE UNIT', line )
			if match :
				diskInfo['enhancedEraseTime'] = match.group(1)


		# Security enabled
		if 'Security level high' in line:
				diskInfo['securityEnabled'] = True;

	#print(diskInfo)
	# If there is no security section, return False
	if not securitySection:
		return False

	return diskInfo

def ChooseDisk():
	# Build the zenity list items
	listItems = []
	for device, diskInfo in disks.items():
		# Disk device
		listItems.append( device )
		# Model
		listItems.append( diskInfo['model'] )
		# Is it password protected?
		listItems.append( 'Yes' if diskInfo['securityEnabled'] else 'No' )
		# Is the disk frozen?
		listItems.append( 'Yes' if diskInfo['frozen'] else 'No' )
		# Is the disk locked?
		listItems.append( 'Yes' if diskInfo['locked'] else 'No' )
		# Enhanced Erase time
		listItems.append( diskInfo['enhancedEraseTime'] or 'Not available' )
		# Erase time
		listItems.append( diskInfo['eraseTime'] or 'Not available' )

		#print( "List Items: {0}".format( listItems ) )

	selection = subprocess.run( ["zenity", "--list", '--width={0}'.format( listWidth ), '--title="Disk selection"', '--column=Device', '--column=Model', '--column=Password protected', '--column=Frozen?', '--column=Locked?', '--column=enhancedErase', '--column=erase' ] + listItems, stdout=subprocess.PIPE, universal_newlines = True ).stdout.splitlines()[0]
	print( "Selected disk: {0} caca".format( selection ) )
	return selection

def CheckFrozenDisk( disk ):
	if disk['frozen']:
		message = "Disk {0} is frozen.\n\nYou can try sleeping the computer and waking it up.".format( selection )
		selection = subprocess.run( [ "zenity",  '--error', '--no-wrap', '--text=' + message ] ).returncode
		# TODO: go back
		sys.exit(0)
	return False

def CheckLockedDisk( disk ):
	if disk['locked']:
		message = "Disk {0} is locked.\n\nYou can try rebooting the computer or fiddling with hdparm.".format( selection )
		selection = subprocess.run( [ "zenity",  '--error', '--no-wrap', '--text=' + message ] ).returncode
		# TODO: go back
		sys.exit(0)
	return False

def ConfirmErase( disk ):
	methodMsg = ''
	if disk['enhancedErase']:
		methodMsg = 'enhanced erase'
		timeToErase = disk['enhancedEraseTime']
	else:
		methodMsg = 'erase'
		timeToErasetime = disk['eraseTime']

	message = "Are you really sure?\n\nDisk {0} will take {1} minute(s).\n\nThe computer can not be powered off during this process, nor the disk accessed.".format( methodMsg, timeToErase )
	selection = subprocess.run( [ "zenity",  '--question', '--no-wrap', '--text=' + message ] ).returncode

	print( "Selection: {0}".format( selection ) )
	# If the user aborted, exit
	return selection == 0

# Set master password & lock the drive
def LockDisk( disk ):
	process = subprocess.run( ['hdparm', '--user-master', '{0}'.format( masterUser ), '--security-set-pass', '{}'.format( securityPassword ), '/dev/{}'.format( disk )], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines = True )

	print ('Lock returncode = {0}, output = {1}'.format( process.returncode, process.stdout ) )
	if process.returncode != 0 :
		message = 'hdparm failed locking the drive {0}, returned ({1}) "{2}"'.format( disk, process.returncode, process.stdout )
		subprocess.run( [ "zenity",  '--error', '--no-wrap', '--text=' + message ] )
		sys.exit(0)

def EraseTimeout():
	return False

disks = ListDisks()


#print( disks )

disk = ChooseDisk()
diskInfo = disks[ disk ]


# Check if the selected disk is frozen and not locked
CheckFrozenDisk( diskInfo )
CheckLockedDisk( diskInfo )

# Ask for confirmation
if not ConfirmErase( diskInfo ):
	sys.exit( 0 )

# Otherwise, go ahead

# Lock the drive
LockDisk( disk )
# And issue the erase command

# TODO: It might be interesting to capture the output and display it
timeToErase = diskInfo['eraseTime']

startTime = time.time()
# Expected end time
endTime = startTime + int( timeToErase ) * 60
# Current time
currTime = startTime

endTimeStr = time.ctime( endTime )
message = 'Erasing the drive {0}.\n\nThis process might take up to {1} minutes and shall be done by {2}, please be patient'.format( disk, timeToErase, endTimeStr )

# Progress dialog: async process
progressProc = subprocess.Popen( [ "zenity",  '--progress', '--no-cancel', '--percentage=0', '--text=' + message ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE )

# Now launch the hdparm process
if dryRun:
	# Use this for a dry run
	hdparmProc = subprocess.Popen( [ "sleep",  '{}'.format( int( timeToErase ) * 60 ) ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
else:
	# TODO: use enhanced if available
	hdparmProc = subprocess.Popen( ['hdparm', '--user-master', '{0}'.format( masterUser ), '--security-erase', '{}'.format( securityPassword ), '/dev/{}'.format( disk )], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT )

# Update the progress bar every now and then depending on the run time
# But do not update faster than every 5 seconds
updateInterval = max( minProgBarUpdateInterval, float( timeToErase ) * 60.0  / 100.0 )
print( "Updating every {0} secs".format ( updateInterval ) )

while currTime < endTime:
	currTime = time.time()
	# Current progress (based on elapsed time)
	x = ( currTime - startTime ) / ( endTime - startTime ) * 100
	print( "Sending {}".format( x ) )
	progressProc.stdin.write( "{}\n".format( x ).encode() )
	progressProc.stdin.flush()
	#progressProc.communicate()
	time.sleep( updateInterval )

# hdparm should be done by now. Wait a bit (but not too much)
try:
	hdparmCode = hdparmProc.wait( hdparmTimeout )
	print( "hdparm finished successfully" )
except TimeoutExpired:
	EraseTimeout()

print( "Process not finished yet" )
# if the process has not finished, wait for it
progressProc.stdin.close()
progressProc.wait()

# Check if drive is locked
# If that's the case, unlock and display an error message

# TODO check for zeroes in the first X bytes of the drive (or randomly)
