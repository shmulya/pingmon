import subprocess, time

tmp = 0

while True:
    args = ['/usr/bin/python','/home/shmulya/Documents/LiClipse Workspace/videomonitoring/monitor2.py']
    if tmp == 0:
        mon = subprocess.Popen(args)
        tmp = 1
    else:
        if open('./data/tr','r').read() == '1':
            mon.terminate()
            print 'stoped'
            time.sleep(3)
            mon = subprocess.Popen(args)
            print 'started'
            open('./data/tr','w').write('0')
        elif open('./data/tr','r').read() == '0':
            time.sleep(2)
