#!/usr/bin/env python

from Adafruit_PWM_Servo_Driver import PWM
import time
import math
import threading

# Controller at i2c address 0x40
pwm = PWM(0x40, debug=False)
#pwm2 = PWM(0x41, debug=False)

# Store offsets, cheap analog servos aren't that precise
servoCenter = [410,430,395,360,390,370,370,380,380,360,390,400,480,370,380,370, 16, 17, 18]
servoMin = [170,185,150,135,155,140,140,140,140,135,150,160,220,135,145,140, 16, 17, 18]
servoMax = [650,660,650,620,640,620,640,630,640,610,635,635,670,630,645,645, 16, 17, 18]

# Interpolation steps
stepPerS = 8

# Max height
floor = 70

# Set frequency to 60 Hz, max for servos
pwm.setPWMFreq(60)

lock = threading.Lock()

class runMovement(threading.Thread):
	def __init__(self,function,*args):
		threading.Thread.__init__(self)
		self.function=function
		self.args = args
		self.lock = lock
		self.start()

	def run(self):
		self.function(*self.args)

class hexapod():
	def __init__(self):
		self.RF = leg('rightFront',15,11,10)
		self.RM = leg('rightMid',14,9,8)
		self.RB = leg('rightBack',16,7,6)
		
		self.LF = leg('leftFront',12,1,0)
		self.LM = leg('leftMid',13,3,2)
		self.LB = leg('leftBack',17,5,4)
		
		self.legs = [self.RF,self.RM,self.RB,self.LF,self.LM,self.LB]
		
		self.neck = neck(18)
		
		self.tripod1 = [self.RF,self.RB,self.LM]
		self.tripod2 = [self.LF,self.LB,self.RM]

class neck():
	def __init__(self,servoNum):
		self.servoNum = servoNum

	def set(self,deg):
		setAngle(servoNum, deg)

class leg():

	def __init__(self,name,hipServoNum,kneeServoNum,ankleServoNum,simOrigin=(0,3,0)):
		self.name = name
		self.hipServoNum = hipServoNum
		self.kneeServoNum = kneeServoNum
		self.ankleServoNum = ankleServoNum

	def hip(self, deg):
		if deg == "sleep":
			pwm.setPWM(self.hipServoNum, 0, 0)
		else:
			setAngle(self.hipServoNum, deg)

	def knee(self, deg):
		if deg == "sleep":
			pwm.setPWM(self.kneeServoNum, 0, 0)
		else:
			setAngle(self.kneeServoNum, deg)

	def ankle(self, deg):
		if deg == "sleep":
			pwm.setPWM(self.ankleServoNum, 0, 0)
		else:
			setAngle(self.ankleServoNum, deg)

	def setHipDeg(self,endHipAngle,stepTime=1):
		runMovement(self.setHipDeg_function, endHipAngle,stepTime)
		
	def setHipDeg_function(self,endHipAngle,stepTime):
		#print "endHipAngle: %s,servoNum: %s" % (endHipAngle, self.hipServoNum)
		
		'''
		# Non-interpolated version
		setAngle(self.hipServoNum, endHipAngle)
		time.sleep(stepTime)
		'''
		
		lock.acquire()
		currentHipAngle = getAngle(self.hipServoNum)
		lock.release()
		
		hipMaxDiff = float(endHipAngle-currentHipAngle)
		
		steps = range(int(stepPerS*stepTime))
		stepDelay = 1/float(stepPerS * stepTime)
		for i,t in enumerate(steps):
			# TODO: implement time-movements the servo commands sent for far fewer
			#       total servo commands
			hipAngle = (hipMaxDiff/len(steps))*(i+1)
			try:
				anglNorm=hipAngle*(180/(hipMaxDiff))
			except:
				anglNorm=hipAngle*(180/(1.0))
			hipAngle = currentHipAngle+hipAngle
			setAngle(self.hipServoNum, hipAngle)
			
			#wait for next cycle
			time.sleep(stepDelay)

	def setFootY(self,footY,stepTime=1):
		runMovement(self.setFootY_function, footY,stepTime)
		
	def setFootY_function(self,footY,stepTime):
		# TODO: max steptime dependent
		# TODO: implement time-movements the servo commands sent for far fewer
		#       total servo commands
		
		#print "footY: %s" % footY
		if (footY < 75) and (footY > -75):
			kneeAngle = math.degrees(math.asin(float(footY)/75.0))
			ankleAngle = 90.0-kneeAngle
			setAngle(self.kneeServoNum, kneeAngle)
			setAngle(self.ankleServoNum,-ankleAngle)
	
	def replantFoot(self,endHipAngle,stepTime=1, height=60):
		runMovement(self.replantFoot_function, endHipAngle,stepTime, height)
		
	def replantFoot_function(self,endHipAngle,stepTime, height):
		# Smoothly moves a foot from one position on the ground to another in time seconds
		# TODO: implement time-movements the servo commands sent for far fewer total servo
		#       commands
		
		'''
		# Non-interpolated version
		# Raise boot to max
		self.setFootY(0,stepTime=0)
		# Rotate hip
		setAngle(self.hipServoNum, endHipAngle)
		# sleep a bit to adhere to steptime param
		time.sleep(stepTime/2)
		# Lower foot to height
		self.setFootY(height,stepTime=0)
		'''

		lock.acquire()
		currentHipAngle = getAngle(self.hipServoNum)
		lock.release()
		
		hipMaxDiff = float(endHipAngle - currentHipAngle)
			
		steps = range(int(stepPerS*stepTime))
		stepDelay = 1/float(stepPerS * stepTime)
		for i,t in enumerate(steps):
	
			#print "replantFoot %s:\ti: %s cur: %s end: %s max: %s" % (self.hipServoNum, i, currentHipAngle, endHipAngle, hipMaxDiff)
			hipAngle = (hipMaxDiff/len(steps))*(i+1)
			#print "hip angle calc'd:",hipAngle
			
			#calculate the absolute distance between the foot's highest and lowest point
			footMax = 0
			footMin = height
			footRange = abs(footMax-footMin)
			
			#normalize the range of the hip movement to 180 deg
			try:
				anglNorm=hipAngle*(180/(hipMaxDiff))
			except:
				anglNorm=hipAngle*(180/(1.0))
			#print "normalized angle:",anglNorm
			
			#base footfall on a sin pattern from footfall to footfall with 0 as the midpoint
			footY = footMin-math.sin(math.radians(anglNorm))*footRange
			#print "calculated footY",footY
			
			#set foot height
			self.setFootY(footY,stepTime=0)
			hipAngle = currentHipAngle+hipAngle
			setAngle(self.hipServoNum, hipAngle)
			
			#wait for next cycle
			time.sleep(stepDelay)


def setAngle(channel, angle):
	if channel > 15:
		#print "servoNum out of range: %s" % channel
		return
	
	if angle < -90:
		angle = -90
	if angle > 90:
		angle = 90
	if angle == 0:
		pwmvalue = servoCenter[channel]
	if angle > 0:
		pwmvalue = servoCenter[channel] + (angle/90.0)*abs(servoMax[channel] - servoCenter[channel])
	if angle < 0:
		pwmvalue = servoCenter[channel] + (angle/90.0)*abs(servoCenter[channel] - servoMin[channel])
	#print "\t\t\t%s: angle: %s, pwmvalue: %s" % (channel, angle, pwmvalue)

	lock.acquire()
	if channel < 16:
		pwm.setPWM(channel, 0, int(pwmvalue))
	else:
		pwm2.setPWM(channel - 16, 0, int(pwmvalue))
	lock.release()

def getAngle(channel):
	if channel > 15:
		#print "servoNum out of range: %s" % channel
		return 0

	if channel < 16:
		pwmvalue = pwm.getPWM(channel)
	else:
		pwmvalue = pwm2.getPWM(channel)
			
	if pwmvalue > servoCenter[channel]:
		angle = 90.0*(pwmvalue - servoCenter[channel])/float(servoMax[channel] - servoCenter[channel])
	else:
		angle = 90.0*(servoCenter[channel] - pwmvalue)/float(servoCenter[channel] - servoMin[channel])
	#print "%s: angle %s" % (channel, angle)
	if (angle > -90) and (angle < 90):
		return angle
	else:
		return 0