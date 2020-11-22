import sys
import random
import signal
import threading
from socket import socket, SOCK_DGRAM, AF_INET, SOCK_STREAM
from struct import *

port = int(sys.argv[1])
protocol = sys.argv[2]
file = sys.argv[3]
windowSize = int(sys.argv[4])
TIMEOUT = int(sys.argv[5])
MSS = int(sys.argv[6])
BIT_ERROR_PROBABILITY = float(sys.argv[7]) # Probability for bit error
f = open(file, 'r')
data = f.read()

print ("|-|-|-|-|-|-|-|-|-| Sender info |-|-|-|-|-|-|-|-|-| ")
print ("host: " + host)
print( "protocol: " + protocol)
print ("Window size: " + str(windowSize))
print ("Timeout: " + str(TIMEOUT))
print ("MSS: " + str(MSS))
print ("Port: " + str(port))
print("len: "+str(len(data)))
print ("Number of packets to send: " + str((len(data) / MSS) + 1))

seqNum = 0
firstInWindow = -1
lastInWindow = -1
lastAcked = -1
numAcked = -1

sendComplete = False
ackedComplete = False

sendBuffer = []
timeoutTimers = []

clientSocket = socket(AF_INET, SOCK_STREAM)
ip = input("Enter your IP address: ")
lock = threading.Lock()


def CalculateChecksum(cs):
	if len(cs) % 2 != 0:
		cs  = cs + str(0)
	iterator = 0
	checksum = 0
	while iterator < len(cs):
		cs1 = ord(cs[iterator])*128 + ord(cs[iterator+1])
		cs2 = 32767 - cs1
		cs3 = checksum + cs2
		checksum = (cs3 % 32768) + (cs3 / 32768)
		iterator += 2
	return (32767 - checksum)

## Get the next byte to send from the message string
def GetNextByte():
	global sendComplete
	global data

	if data:
		nextByte = data[0]
		data = data[1:len(data)]
	else:
		nextByte = ''
		sendComplete = True
	return nextByte

## Construct the next segment of the message
def GetMessage():
	global sendComplete
	global MSS

	message =''
	while len(message) < MSS and not sendComplete:
		message+= GetNextByte()
	return message

## Resend packets in the window
def ResendPackets():
	global MSS
	global sendBuffer
	global clientSocket
	global TIMEOUT
	global timeoutTimers
	global lastInWindow
	global firstInWindow
	global host
	global port
	global windowSize

	iterator = firstInWindow
	while iterator <= lastInWindow:
		if sendBuffer[iterator % windowSize] != None:
			packet = sendBuffer[iterator % windowSize]
			print ("Resending packet: S" + str(iterator) + "; Timer started")
			clientSocket.sendto(packet, (ip, port))
			timeoutTimers[iterator % windowSize] = TIMEOUT
		iterator += 1

## Last packet will header all 1s
def CreateLastPacket():
	header = int('1111111111111111', 2)
	checksum = int('0000000000000000', 2)
	return pack('IHH', seqNum, checksum, header)

## Keep track of the timeout values which are sent to the server
def Signalhandler(signum, _):
	global firstInWindow
	global lastInWindow
	global sendBuffer
	global lock
	global timeoutTimers
	global windowSize

	# If all acknowledgements received
	if ackedComplete:
		return

	# Protocol = Go back N
	if protocol == "GBN":
		for i, eachtimer in enumerate(timeoutTimers):
			timeoutTimers[i] = eachtimer - 1

		if len(timeoutTimers) > (firstInWindow % windowSize) and timeoutTimers[firstInWindow % windowSize] == 0:
			print ("Timeout, sequence number =", firstInWindow)
			lock.acquire()
			ResendPackets()
			lock.release()

	# Protocol = Selective repeat
	elif protocol == "SR":
		iterator = firstInWindow
		while iterator <= lastInWindow:
			timeoutTimers[iterator % windowSize] = timeoutTimers[iterator % windowSize] - 1
			lock.acquire()
			if timeoutTimers[iterator % windowSize] < 1 and sendBuffer[iterator % windowSize] != None:
				print ("Timeout, sequence number =", iterator)
				packet = sendBuffer[iterator % windowSize]
				print ("Resending packet: S" + str(iterator) + "; Timer started")
				clientSocket.sendto(packet, (host, port))
				timeoutTimers[iterator % windowSize] = TIMEOUT
			lock.release()
			iterator = iterator + 1

## Look for acknowledgements from the server
def LookforACKs():
	global firstInWindow
	global sendBuffer
	global windowSize
	global clientSocket
	global numAcked
	global seqNum
	global ackedComplete
	global sendComplete
	global lastAcked
	global lastInWindow

	# Protocol = Go back N
	if protocol == "GBN":

		while not ackedComplete:
			packet, addr = clientSocket.recvfrom(8)
			ack = unpack('IHH', packet)
			ackNum = ack[0]

			if ackNum == seqNum :
				print("Received ACK: ", ackNum)
				lock.acquire()
				iterator = firstInWindow
				while iterator <= lastInWindow:
					sendBuffer[iterator % windowSize] = None
					timeoutTimers[iterator % windowSize] = 0
					lastAcked = lastAcked + 1
					firstInWindow = firstInWindow + 1
				lock.release()

			elif ackNum == lastAcked + 1 :
				print("Received ACK: ", ackNum)
				lock.acquire()
				sendBuffer[ackNum % windowSize] = None
				timeoutTimers[ackNum % windowSize] = 0
				lastAcked = lastAcked + 1
				firstInWindow = firstInWindow + 1
				lock.release()


				# If all packets sent and all acknowledgements received
			if sendComplete and lastAcked >= lastInWindow:
					ackedComplete = True


	# Protocol = Selective repeat
	elif protocol == "SR":
		print ("wutt")
		while not ackedComplete:
			packet, addr = clientSocket.recvfrom(8)
			ack = unpack('IHH', packet)
			ackNum = ack[0]

			if ackNum == firstInWindow:
				print ("Received ACK: ", ackNum)
				lock.acquire()
				sendBuffer[firstInWindow % windowSize] = None
				timeoutTimers[firstInWindow % windowSize] = 0
				lock.release()
				numAcked = numAcked + 1
				firstInWindow = firstInWindow + 1

			elif ackNum >= firstInWindow & ackNum <= lastInWindow :
				sendBuffer[ackNum % windowSize] = None
				timeoutTimers[ackNum % windowSize] = 0
				numAcked += 1

			if sendComplete and numAcked >= lastInWindow:
				print ("bum")
				ackedComplete = True

# Start thread looking for acknowledgements
threadForAck = threading.Thread(target=LookforACKs, args=())
threadForAck.start()

signal.signal(signal.SIGALRM, Signalhandler)
signal.setitimer(signal.ITIMER_REAL, 0.01, 0.01)

firstInWindow = 0

# Send packets
while not sendComplete:
	toSend = lastInWindow + 1
	msg = GetMessage()
	header = int('0101010101010101', 2)
	cs = pack('IH' + str(len(msg)) + 's', seqNum, header, msg)
	checksum = CalculateChecksum(cs)
	packet = pack('IHH' + str(len(msg))+'s', seqNum, checksum, header, msg)

	if toSend < windowSize:
		sendBuffer.append(packet)
		timeoutTimers.append(TIMEOUT)
	else:
		sendBuffer[toSend % windowSize] = packet
		timeoutTimers[toSend % windowSize] = TIMEOUT

	print ("Sending S" + str(seqNum) + "; Timer started")

	clientSocket.sendto(packet, (ip, port))

	lastInWindow = lastInWindow + 1
	seqNum = seqNum + 1

while not ackedComplete:
	pass

clientSocket.sendto(CreateLastPacket(), (ip, port))
clientSocket.close()
f.close()
print("bye.SELIMTOS")