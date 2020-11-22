import sys
import random
from socket import socket, SOCK_DGRAM, AF_INET, SOCK_STREAM
from struct import *

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


## Verify checksum of the packet received
def Checksum(cs, seq, header, data):
	if (seq + header) % 18 == 0:
		data = data[::-1]

	checksum = pack('IH'+str(len(data))+'s', seq, header, data)
	res= CalculateChecksum(checksum)
	if res == cs :
		return True
	else:
		return  False

## Send acknowledgement
def SendAck(seqNum, clientAddr, sock):
	allZeros = int('0000000000000000', 2)
	header = int('1010101010101010', 2)
	packet = pack('IHH', seqNum, allZeros, header)
	sock.sendto(packet, clientAddr)

def main():
	port = int(sys.argv[1])
	host = '127.0.0.1'
	protocol = sys.argv[2]
	file = sys.argv[3]
	windowSize = int(sys.argv[4])
	timeout = int(sys.argv[5])
	mss = int(sys.argv[6])
	prob = float(sys.argv[7])

	print("|-|-|-|-|-|-|-|-|-| Receiver info |-|-|-|-|-|-|-|-|-|")
	print("Hostname: " + host)
	print("Port: " + str(port))
	print("Protocol: " + protocol)
	print("File: " + file)
	print("Window size: " + str(windowSize))
	print("Timeout: "+ str(timeout))
	print("MSS:  "+ str(mss))

	serverSocket = socket(AF_INET, SOCK_STREAM)
	serverSocket.bind((host, port))
	serverSocket.listen(1)

	seqNum = 0
	firstInWindow = 0
	lastInWindow = firstInWindow + windowSize - 1
	lastReceived = -1
	received = []
	receiveBuffer = []

	for i in range(windowSize):
		received.append(0)
		receiveBuffer.append(None)

	while True:
		connectionSocket, addr = serverSocket.accept()
		message = connectionSocket.recvfrom(1024)
		packet = unpack('IHH'+str(len(message) - 8)+'s', message)

		 # When the last packet is received, close the server
		if packet[2] == int('1111111111111111', 2):
			break;

		if prob < random.random():
			seqNum = packet[0]
			checksum =packet[1]
			header = packet[2]
			data = packet[3]
			print("Packet received: S" + str(seqNum))
			print(len(data))
			if protocol == "GBN":

				if Checksum(checksum, seqNum, header, data):
					if seqNum == lastReceived + 1:
						print ("ACK sent for S" + str(seqNum))
						SendAck(seqNum, addr, serverSocket)
						lastReceived = seqNum
					elif seqNum != lastReceived + 1 and seqNum > lastReceived + 1:
						if lastReceived >= 0:
							print ("(Packet out of order, discarded): last received packet in sequence: packet " \
								  + str(lastReceived))
					else:
						print ("ACK sent for S" + str(seqNum))
						SendAck(seqNum, addr, serverSocket)
						lastReceived = seqNum
				else:
					print ("Packet discarded. Checksum not matching." )

			# Protocol = Selective repeat
			elif protocol == "SR":

				if seqNum < firstInWindow:
					print( "Old packet received: S" + str(seqNum))
					SendAck(seqNum, addr, serverSocket)
				else:
					if Checksum(checksum, seqNum, header, data):
						if seqNum >= firstInWindow and seqNum <= lastInWindow:
							if seqNum == firstInWindow:
								receiveBuffer[firstInWindow % windowSize] = None
								received[firstInWindow % windowSize] = 0
								firstInWindow += 1
								lastInWindow += 1
							elif received[seqNum % windowSize] == 0:
								receiveBuffer[seqNum % windowSize] = packet
								received[seqNum % windowSize] = 1
						print ("ACK sent for S" + str(seqNum))
						SendAck(seqNum, addr, serverSocket)
					else:
						print ("Packet discarded. Checksum not matching.")
		else:
			print ("Packet S" + str(packet[0]) + " lost. (Info for simulation)")

	connectionSocket.close()


if __name__ == '__main__':
	main()