#!/usr/bin/python3
import socket
import struct
import sys
import errno
from select import select
from enum import Enum
import functools

UTF = 'utf-8'

globals = {
        'na': 0,
        'nb': 0,
        'nc': 0,
        'maxPlaying' : 0,
        'maxWaiting' : 0,
        'PORT' : 6444,
        'optimal' : False
    }

class AcceptStatus(Enum):
    PLAY = 0
    WAIT = 1
    REJECT = 2

class ClientStatus(Enum):
    READY_TO_SEND = 0
    SENDING = 1
    READY_TO_READ = 2
    READING = 3

# Gets command line input
def getConsoleInput():
    inputLen = len(sys.argv)
    if not(inputLen >= 6  or inputLen <= 10) :
        print("Invalid number of arguements for nim-server")
        print("Should be of format : heapA heapB heapC num_players wait-list-size [PORT] [--optimal-startegy] [--multithreading timer] ")
        sys.exit(0)
    globals['na'] = int(sys.argv[1])
    globals['nb'] = int(sys.argv[2])
    globals['nc']= int(sys.argv[3])
    globals['maxPlaying'] = int(sys.argv[4])
    globals['maxWaiting'] = int(sys.argv[5])
    if(inputLen >= 7): # can add check to viable PORT number , i.e. > 1024
        if sys.argv[6].isdigit():
            globals['PORT'] = int(sys.argv[6])
        else:
            print("Error: PORT number specified is invalid.")
            sys.exit(0) 
    globals['optimal'] = (inputLen >= 8 and sys.argv[7] == "--optimal-strategy")
    # if inputLen >= 10 and both the flag and timer are correct we can add support for multithreading and timer


def initUser(socket,accept_status):
    if(accept_status == AcceptStatus.PLAY):
        messageTag = 'i'
    elif(accept_status == AcceptStatus.WAIT):
        messageTag = 'w'
    else:
        messageTag = 'r'
    return {
        'acceptStatus' : accept_status,
        'socket' : socket,
        'heaps' : [globals['na'],globals['nb'],globals['nc']] , 
        'messageTag' : messageTag,
        'gameOver' : False,
        'status' : ClientStatus.READY_TO_SEND,
        'sendingBuffer' : struct.pack(">ciii",messageTag.encode(UTF),globals['na'],globals['nb'],globals['nc']),
        'recvChunks' : [],
        'bytesRecv' : 0,
        'disconnected' : False
    }

# DB methods
def addUser(db,userSocket,accept_status):
    userId = userSocket.fileno()
    user_data = initUser(userSocket,accept_status)
    db[userId] = user_data

def deleteUser(db,userId):
    del db[userId]

# Recv and Send msg
def recvMsg(db,client):
    STRUCT_SIZE = 33
    try:
        data = db[client]['socket'].recv(1024)
    except OSError as error:
        if error.errno == errno.ECONNREFUSED:
            # client disconnect from server
            db[client]['disconnected'] = True
    if data == b'':
        # client disconnect from server
        db[client]['disconnected'] = True
    # Some data was recieved
    db[client]['bytesRecv'] += sys.getsizeof(data)-STRUCT_SIZE 
    db[client]['recvChunks'].append(data)

def sendMsg(db, client):
    print(f"message for {client} is {db[client]['sendingBuffer']}")
    try:
        if len(db[client]['sendingBuffer']) != 0:
            ret = db[client]['socket'].send(db[client]['sendingBuffer'])
            db[client]['sendingBuffer'] = db[client]['sendingBuffer'][ret:]
    except OSError as error:
        # client disconnect from server
        db[client]['disconnected'] = True

# Preforms shutdown to the socket - i.e. checks for 'leftover' data on recv buffer
def shutdownSocket(conn):
    conn.shutdown(socket.SHUT_WR)
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
        except OSError as error:
            break
    conn.close()

# GAMEPLAY methods
def handleNewMove(db,client,msg):
    updateHeapsServer = updateHeapServerOptimal if globals['optimal'] else updateHeapsServerNaive
    heapIndex, amount = parseRecvInput(msg)
    print(f"Incoming heaps for {client} are {db[client]['heaps']}")
    # Make game move and set messageTag:
    if(heapIndex >= 3): # Quit current game
        db[client]['disconnected'] = True
    if(not checkValid(db[client]['heaps'],heapIndex,amount)):
        messageTag = 'x'
        updateHeapsServer(db[client]['heaps'])
        if(checkForWin(db[client]['heaps'])):
            # server wins - last client move was invalid
            messageTag = 't'
            db[client]['gameOver'] = True
    else:
        messageTag = 'g'
        updateHeapsClient(db[client]['heaps'],heapIndex,amount)
        if(checkForWin(db[client]['heaps'])):
            # client wins - last client move was valid
            messageTag = 'c'
            db[client]['gameOver'] = True
        else:
            updateHeapsServer(db[client]['heaps'])
            if(checkForWin(db[client]['heaps'])):
                # server wins - last client move was valid
                messageTag = 's'
                db[client]['gameOver'] = True
    print(f"Outgoing heaps for {client} are {db[client]['heaps']}")
    return struct.pack(">ciii",messageTag.encode(UTF),db[client]['heaps'][0],db[client]['heaps'][1],db[client]['heaps'][2])

# Gets char as heapId
# 'A'/'B'/'C' returns 0,1,2 respectivly.
# 'Q' return 3
# Any other heapId (invalid) returns -1 
def parseHeapId(heapId):
    return {
        'A' : 0,
        'B' : 1,
        'C' : 2,
        'Q' : 3
    }.get(heapId,-1)

# Client input parser
# param - a bytes object
# Returns heaps array index to look for , or invalid index for quit / invalid move
# Returns amount of die to remove if heapIndex is valid
def parseRecvInput(bytesRecv):
    dataRecv = struct.unpack(">ci",bytesRecv)
    heapId , amount = dataRecv
    heapId = heapId.decode(UTF)
    heapIndex = parseHeapId(heapId)
    return heapIndex,amount

# Checks if current client move is valid
# 0 <= heapIndex <=2 && heaps[heapIndex] >= amount
# returns boolean
# TESTED
def checkValid(heaps,heapIndex,amount):
    if(heapIndex < 0 or heapIndex > 2):
        return False
    if amount <= 0:
        return False
    if(heaps[heapIndex] < amount):
        return False
    else:
        return True
    

def updateHeapServerOptimal(heaps):
    nim_sum = functools.reduce(lambda x, y: x ^ y, heaps) 
    if nim_sum == 0:
        updateHeapsServerNaive(heaps)
        return
    
    for i, heap in enumerate(heaps):
        nim_sum_heap = heap ^ nim_sum
        if nim_sum_heap < heap:
            heaps[i] -= (heaps[i] - nim_sum_heap)
            return

     
# Makes server game move
# Looks for biggest heap and removes 1 from it
# TESTED
def updateHeapsServerNaive(heaps):
    maxNum = max(heaps)
    for i in range(3):
        if heaps[i] == maxNum:
            heaps[i] -= 1
            break

# Makes client game move
# available only if checkValid returns True on params
# TESTED
def updateHeapsClient(heaps,heapIndex,amount):
    heaps[heapIndex] -= amount

# Checks if game was won
# TESTED
def checkForWin(heaps):
    return True if sum(heaps) <= 0 else False


def server():
    # Establish data structures
    db = dict()
    waitingList = []
    currentPlayers = 0
    # Establish a listening socket
    try:
        listenSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        listenSocket.bind(('',globals['PORT']))
        listenSocket.listen(1)
    except OSError as error:
        print('An error occured establishing a server:')
        print(error.strerror)
        if(listenSocket.fileno() >= 0):
            listenSocket.close()
        sys.exit(0)
    while True:
        # retrieve ready sockets from select
        readable, writble, _ = select([listenSocket]+list(db.keys()),list(db.keys()),[])

        # Handle new clients
        if(listenSocket in readable):
            try:
                newClient , addr = listenSocket.accept()
                if(currentPlayers < globals['maxPlaying']):
                    addUser(db,newClient,AcceptStatus.PLAY)
                    currentPlayers += 1
                elif(len(waitingList) < globals['maxWaiting']):
                    addUser(db,newClient,AcceptStatus.WAIT)
                    waitingList.append(newClient)
                else:
                    addUser(db,newClient,AcceptStatus.REJECT)
            except OSError as err:
                print('Failed to accept an incoming connection... ')
                print(err.strerror)
                break
        
        # Handle existing clients - sending messages to client
        for client in writble:
            if(db[client]['status'] == ClientStatus.READY_TO_SEND or db[client]['status'] == ClientStatus.SENDING):
                sendMsg(db,client)
                db[client]['status'] = ClientStatus.SENDING
                # check if need to terminate client
                if(len(db[client]['sendingBuffer']) == 0):
                    #message is fully sent- check if connection should be terminated
                    if(db[client]['acceptStatus'] == AcceptStatus.REJECT or db[client]['gameOver']):
                        db[client]['disconnected'] = True
                    else:
                        db[client]['status'] = ClientStatus.READY_TO_READ
                        db[client]['recvChunks'] = []
                        db[client]['bytesRecv'] = 0

        for client in readable:
            if(client is listenSocket):
                continue
            if(db[client]['status'] == ClientStatus.READY_TO_READ or db[client]['status'] == ClientStatus.READING):
                recvMsg(db,client)
                db[client]['status'] = ClientStatus.READING
                if(db[client]['bytesRecv'] > 5):
                    db[client]['disconnected'] = True
                if(db[client]['bytesRecv'] == 5):
                    # message is fully received - update game status
                    msg = b''.join(db[client]['recvChunks'])
                    print(f"Message was receieved fully w/ {msg}")
                    newMsg = handleNewMove(db,client,msg)
                    db[client]['status'] = ClientStatus.READY_TO_SEND
                    db[client]['sendingBuffer'] = newMsg
                    print(f"New message server has to send is {db[client]['sendingBuffer']}")
                
        
        # Cleanup of disconnected sockets
        for client in list(db.keys()):
            if(db[client]['disconnected']):
                if(db[client]['acceptStatus'] == AcceptStatus.PLAY):
                    currentPlayers -= 1
                    print("A player was removed from the 'playing list'")
                if(db[client]['acceptStatus'] == AcceptStatus.WAIT):
                    # Remove a disconnected waiting client from the waiting list
                    waitingList = [socket for socket in waitingList if socket != db[client]['socket']]
                    print("A player was removed from the 'waiting list'")
                shutdownSocket(db[client]['socket'])
                deleteUser(db,client)
        
        # Get new waiting players to the game
        while(currentPlayers < globals['maxPlaying'] and len(waitingList) > 0):
            newClient = waitingList.pop(0)
            addUser(db,newClient,AcceptStatus.PLAY) # This overwrites his waiting status in db
            currentPlayers += 1
            print(f"client {db[newClient.fileno()]['socket'].fileno()} is now ready to play w/ status {db[newClient.fileno()]['status']}")

    listenSocket.close() # Server Cleanup


#Main function for the program
def main():
    getConsoleInput()
    server()

def test():
    getConsoleInput()


DEBUG = False
func = main if not DEBUG else test
func()
