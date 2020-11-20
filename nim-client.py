#!/usr/bin/python3
import errno
import socket
import struct
import sys

STRUCT_SIZE = 33
UTF = 'utf-8'


# returns True if message sent successfully
def mySendall(clientSoc, byteStep):
    try:
        while len(byteStep) != 0:
            ret = clientSoc.send(byteStep)
            byteStep = byteStep[ret:]
    except OSError as error:
        print("Disconnected from server")
        return False
    return True


# returns bytes object with the data received from server
# return true if message received successfully ,otherwise returns False
def myRecvall(clientSoc, expectedLenInBytes):
    gotSize = 0
    chunks = []
    while gotSize < expectedLenInBytes:
        try:
            data = clientSoc.recv(1024)
        except OSError as error:
            if error.errno == errno.ECONNREFUSED:
                print("Disconnected from server")
            else:
                print(error.strerror + ", exit game")
            return False, b''
        if data == b'':
            print("Disconnected from server")
            return False, b''
        gotSize += sys.getsizeof(data) - STRUCT_SIZE
        chunks.append(data)
    return True, b''.join(chunks)


# Generalized version of shutdownSocketClient
def shutdownSocket(clientSoc):
    clientSoc.shutdown(socket.SHUT_WR)
    while True:
        try:
            data = clientSoc.recv(1024)
            if not data:
                break
        except OSError as error:
            break


# returns bytes object with the data to send to the server- format ">ci"
# return true if user asked for QUIT- Q ,otherwise returns False
def createStep():
    step = input()
    splitStep = step.split()
    if len(splitStep) == 2:
        if splitStep[0] == "Q" or len(splitStep[0]) != 1 or not splitStep[1].isdigit():
            return False, struct.pack(">ci", b'Z', 0)
        else:
            return False, struct.pack(">ci", splitStep[0].encode(UTF), int(splitStep[1]))
    elif len(splitStep) == 1:
        if splitStep[0] == "Q":
            return True, struct.pack(">ci", b'Q', 0)
        else:
            return False, struct.pack(">ci", b'Z', 0)
    else:
        return False, struct.pack(">ci", b'Z', 0)


# returns true if the parameters are valid (3 int >=0 and tav is in {i,g,s,c,x,t}
# otherwise returns false
def checkValidParm(tav, nA, nB, nC):
    if nA < 0 or nB < 0 or nC < 0:
        return False
    if tav == b'i' or tav == b'g' or tav == b's' or tav == b'c' or tav == b'x' or tav == b't':
        return True
    return False


# returns True if game should be continue, otherwise returns False
def parseCurrentPlayStatus(data):
    tav, nA, nB, nC = struct.unpack(">ciii", data)
    valid = checkValidParm(tav, nA, nB, nC)
    if valid:
        if tav == b'i':
            print("nim")
        elif tav == b'g' or tav == b's' or tav == b'c':
            print("Move accepted")
        elif tav == b'x' or tav == b't':
            print("Illegal move")

        print("Heap A: " + str(nA))
        print("Heap B: " + str(nB))
        print("Heap C: " + str(nC))

        if tav == b's' or tav == b't':
            print("Server win!")
            return False
        elif tav == b'c':
            print("You win!")
            return False
        print("Your turn:")
        return True
    else:
        print("server sent invalid message, exit game")
        return False


# while game on and connection is valid, get the heap status, and send the new game move
def startPlay(clientSoc):
    run = True
    while run:
        run, allDataRecv = myRecvall(clientSoc, 13)
        if run and sys.getsizeof(allDataRecv) - STRUCT_SIZE == 13:
            run = parseCurrentPlayStatus(allDataRecv)
            if run:
                quitCommand, bytesNewMove = createStep()

                if not quitCommand:
                    run = mySendall(clientSoc, bytesNewMove)
                else:
                    run = False
        elif run:
            print("server sent invalid message, exit game")
            run = False


# create the first connection
def connectToGame(hostName, port):
    clientSoc = None
    try:
        clientSoc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSoc.connect((hostName, port))
        startPlay(clientSoc)
        shutdownSocket(clientSoc)
    except OSError as error:
        if error.errno == errno.ECONNREFUSED:
            print("Disconnected from server")
        elif error.errno != 107:
            print(str(error.errno) + error.strerror + ", cannot start playing")
    finally:
        if clientSoc is not None:
            clientSoc.close()


# expected 2 arguments- first for hostname, second for port number
# if got 2 or more arguments, use the first two
# one argument belongs to hostname
def main():
    n = len(sys.argv)
    hostName = ""
    port = "6444"
    if n > 2:
        hostName = sys.argv[1]
        port = sys.argv[2]
    elif n > 1:
        hostName = sys.argv[1]
    if port.isdigit():
        connectToGame(hostName, int(port))
    else:
        print("second argument is not a valid port number, cannot start playing")


main()
