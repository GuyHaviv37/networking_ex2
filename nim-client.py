#!/usr/bin/python3
import errno
import socket
import struct
import sys
from enum import Enum
from select import select

STRUCT_SIZE = 33
UTF = 'utf-8'
RECV_MSG_LEN = 13


class CurrentState(Enum):
    USER_INPUT = 1
    GET_MSG = 2
    SEND_MSG = 3


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
    if tav == b'i' or tav == b'g' or tav == b's' or tav == b'c' or tav == b'x' or tav == b't' or tav == b'w' or tav == b'r':
        return True
    return False


# returns True if game should be continue, otherwise returns False, the second return value tells if we are waiting
def parseCurrentPlayStatus(data):
    tav, nA, nB, nC = struct.unpack(">ciii", data)
    valid = checkValidParm(tav, nA, nB, nC)
    if valid:
        if tav == b'i':
            print("Now you are playing against the server!")
            print("nim")
        elif tav == b'g' or tav == b's' or tav == b'c':
            print("Move accepted")
        elif tav == b'x' or tav == b't':
            print("Illegal move")
        elif tav == b'r':
            print("You are rejected by the server.")
            return False, False
        elif tav == b'w':
            print("Waiting to play against the server.")
            return True, True

        print("Heap A: " + str(nA))
        print("Heap B: " + str(nB))
        print("Heap C: " + str(nC))

        if tav == b's' or tav == b't':
            print("Server win!")
            return False, False
        elif tav == b'c':
            print("You win!")
            return False, False
        print("Your turn:")
        return True, False
    else:
        print("server sent invalid message, exit game")
        return False, False


def recvMsg(clientSoc):
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
    return True, data


def sendMsg(clientSoc, byteMsgToSend):
    try:
        if len(byteMsgToSend) != 0:
            ret = clientSoc.send(byteMsgToSend)
            byteMsgToSend = byteMsgToSend[ret:]
    except OSError as error:
        print("Disconnected from server")
        return False, b''
    return True, byteMsgToSend


# return True if user asked to QUIT, otherwise return False
# if user input is not Quit, keep playing- ignore the input
def getInput():
    userInput = input()
    splitUserInput = userInput.split()
    # user input is not Q
    if len(splitUserInput) != 1:
        return False
    return splitUserInput[0] == "Q"


# while game on and connection is valid, get the heap status, and send the new game move
def startPlay(clientSoc):
    keepPlaying = True
    state = CurrentState.GET_MSG
    gotSize = 0
    chunks = []
    byteMsgToSend = b''
    while keepPlaying:
        readable, writable, _ = select([clientSoc, sys.stdin], [clientSoc], [])
        if state == CurrentState.GET_MSG:
            if sys.stdin in readable:
                keepPlaying = not getInput()
                if not keepPlaying:
                    break
            if clientSoc in readable:
                keepPlaying, data = recvMsg(clientSoc)
                if not keepPlaying:
                    break
                gotSize += sys.getsizeof(data) - STRUCT_SIZE
                chunks.append(data)
                if gotSize == RECV_MSG_LEN:
                    allDataRecv = b''.join(chunks)
                    chunks = []
                    gotSize = 0
                    keepPlaying, waiting = parseCurrentPlayStatus(allDataRecv)
                    if waiting:
                        state = CurrentState.GET_MSG
                    else:
                        state = CurrentState.USER_INPUT
                elif gotSize > RECV_MSG_LEN:
                    print("server sent invalid message, exit game")
                    keepPlaying = False
        elif state == CurrentState.SEND_MSG:
            if sys.stdin in readable:
                keepPlaying = not getInput()
                if not keepPlaying:
                    break
            if clientSoc in writable:
                keepPlaying, byteMsgToSend = sendMsg(clientSoc, byteMsgToSend)
                if len(byteMsgToSend) == 0:
                    state = CurrentState.GET_MSG
                    byteMsgToSend = b''
        else:
            if clientSoc in readable:
                try:
                    data = clientSoc.recv(1024)
                except OSError as error:
                    if error.errno == errno.ECONNREFUSED:
                        print("Disconnected from server")
                    else:
                        print(error.strerror + ", exit game")
                    keepPlaying = False
                if data == b'':
                    print("Disconnected from server")
                    keepPlaying = False
            if sys.stdin in readable and keepPlaying:
                quitCommand, byteMsgToSend = createStep()
                if not quitCommand:
                    state = CurrentState.SEND_MSG
                else:
                    keepPlaying = False


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
