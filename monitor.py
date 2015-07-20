from threading import Thread, Event, Lock
from urllib import unquote
import subprocess, time, datetime, smtplib, json, BaseHTTPServer, re, sys, logging, MySQLdb, warnings
from Queue import Queue
from os import path
#import conf

def config():
    
    conffile = open('./data/conf','r')
    conflist = []
    confdict = {}
    
    for line in conffile:
        if line[-1:] == '\n':
            conflist.append(line[:-1].split(' = '))
        else:
            conflist.append(line.split(' = '))    
    
    for k,v in conflist:
        confdict.update({k:v})
    return confdict


conf = config()
failcount = {}
td = {}
queue = Queue()
output = Queue()
global flag, ev, mysql, ex
flag = Event()
flag.set()
ev = Lock()
mysql = MySQLdb.connect(host='localhost', user=conf.get('db_login'), passwd=conf.get('db_password'), db=conf.get('database'))
ex = mysql.cursor()
warnings.simplefilter('ignore')

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
        srcggif = re.search('.gif$', self.path)
        if srcggif != None:
            self.send_response(200)
            self.send_header("Content-type", "image/gif")
            self.end_headers()
            self.wfile.write(open('./data/pages'+self.path,'r').read())
        if self.path == '/': #root_dir
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(open('./data/pages/monitor','r').read())
        elif self.path == '/listedit' or self.path == '/config':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(open('./data/pages'+self.path,'r').read())
        elif self.path == '/jquery.js' or self.path == '/jquery.flot.js' or self.path == '/jquery.datetimepicker.js' or self.path == '/highcharts.js' or self.path == '/jquery.flot.time.js':
            self.send_response(200)
            self.send_header("Content-type", "text/javascript")
            self.end_headers()
            self.wfile.write(open('./data/plugins'+self.path,'r').read())
        elif self.path == '/test1':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(open('.'+self.path,'r').read())            
        elif self.path == '/jquery.datetimepicker.css':
            self.send_response(200)
            self.send_header("Content-type", "text/css")
            self.end_headers()
            self.wfile.write(open('./data/css'+self.path,'r').read())
        else:
            self.send_error(403)
            
    def do_POST(self):
        
        if self.path == '/api':
            content_len = int(self.headers.getheader('content-length', 0))
            post_body = self.rfile.read(content_len)
            post_body = post_body.split('&')
            req = []
            for it in post_body:
                f = it.split('=')
                req.append(f[1])
            if req[0] == 'hostlistsave':
                global flag
                flag.wait()
                flag.clear()
                try:
                    open('./data/list','w').write(req[1].replace('%0A','\n'))
                except IndexError:
                    self.send_error(406)
                else:
                    self.send_response(200)
                    self.end_headers()
                    global log50
                    log50 = {}
                flag.set()
            elif req[0] == 'hostlistget':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                f = open('./data/list','r').read()
                self.wfile.write(json.dumps(f.split('\n')))
            elif req[0] == 'plotget':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(open('./data/json','r').read())
            elif req[0] == 'config':
                try:
                    conf_str = unquote(req[1])
                except IndexError:
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(config_parser())
                else:
                    self.send_response(200)
                    conf_str = conf_str.replace(':', ' = ')
                    conf_str = conf_str.replace(';', '\n')
                    config_saver(conf_str)
            elif req[0] == 'log':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                try:
                    host,start,end=req[1],req[2],req[3]
                except IndexError:
                    self.wfile.write(sql_get())
                except KeyError:
                    self.wfile.write(sql_get())
                else:
                    self.wfile.write(sql_get(host,datetime.datetime.fromtimestamp(int(start)/1000),datetime.datetime.fromtimestamp(int(end)/1000)))
            elif req[0] == 'adates':
                dates = sql_tables_show()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(dates))
            elif req[0] == 'log50s':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                a = datetime.datetime.now()
                b = a - datetime.timedelta(seconds=500)
                f = open('./data/list','r').read()
                tmp = f.split('\n')
                ress = {}
                for val in tmp:
                    sql = "SELECT * FROM t%s WHERE ts<'%s' AND ts>'%s' AND host='%s'"%(str(a.date()).replace('-',''),a,b,val)
                    sended = {}
                    #global ev
                    ev.acquire()
                    ex.execute(sql)
                    mysql.commit()
                    ev.release()
                    datat = ex.fetchall()
                    for rec in datat:
                        host,ts,val = rec
                        try:
                            ress[host].append([(int(time.mktime(ts.timetuple()))+3*3600)*1000,val])
                        except KeyError:
                            ress.update(dict([(host,[[(int(time.mktime(ts.timetuple()))+3*3600)*1000,val]])]))
                for key in ress:
                    sended.update(dict([(key,ress[key][-50:])]))
                self.wfile.write(json.dumps(sended,sort_keys=True))
            else:
                self.send_error(405) 
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(open('./data/json','r').read())        
    def log_message(self, format, *args):
        logstr = '[%s] - %s %s\n'%(self.log_date_time_string(),self.address_string(),format%args)
        logging.info(logstr)

def sql_tables_show():
    #global ev
    ev.acquire()
    resu = []
    ex.execute("SHOW TABLES;")
    mysql.commit()
    tables = ex.fetchall()
    for rec in tables:
        tmp = rec[0][1:]
        resu.append(tmp[:4]+'-'+tmp[4:6]+'-'+tmp[6:])
    ev.release()
    return resu

def sql_get(conchost=None,start=None,end=None):
    if end == None:
        end = datetime.datetime.now()
    if start == None:
        start = end - datetime.timedelta(seconds=3600)
    if conchost == None:
        conchost = ''
    if (end.day-start.day)+1 > 1:
        ticktack = 1
        res = {}
        tmp1 = start
        dt = datetime.timedelta(seconds=3600*24)
        while ticktack <= (end.day-start.day)+1:
            tmp = end
            if ticktack == (end.day-start.day)+1:
                sql = "SELECT * FROM t%s WHERE host='%s' AND ts<'%s' AND ts>'%s'"%(str(tmp1.date()).replace('-',''),conchost,end,start)
            else:
                sql = "SELECT * FROM t%s WHERE host='%s' AND ts<'%s' AND ts>'%s'"%(str(tmp1.date()).replace('-',''),conchost,tmp.replace(hour=23,minute=59,second=59),start)
            tmp1 = tmp1+dt
            global ev
            ev.acquire()
            try:
                ex.execute(sql)
            except MySQLdb.ProgrammingError, e:
                try:
                    print "MySQL Error [%d]: %s" % (e.args[0], e.args[1])
                    ev.release()
                except IndexError:
                    print "MySQL Error: %s" % str(e)
                    ev.release()
            else:
                mysql.commit()
                ev.release()
                data = ex.fetchall()
                for rec in data:
                    host,ts,val = rec
                    try:
                        res[host].append([(int(time.mktime(ts.timetuple()))+3*3600)*1000,val])
                    except KeyError:
                        res.update(dict([(host,[[(int(time.mktime(ts.timetuple()))+3*3600)*1000,val]])]))
                ticktack += 1
    else:
        sql = "SELECT * FROM t%s WHERE host='%s' AND ts<'%s' AND ts>'%s'"%(str(start.date()).replace('-',''),conchost,end,start)
        #global ev
        ev.acquire()
        res = {}
        try:
            ex.execute(sql)
        except MySQLdb.ProgrammingError, e:
            try:
                print "MySQL Error [%d]: %s" % (e.args[0], e.args[1])
            except IndexError:
                print "MySQL Error: %s" % str(e)
                ev.release()
            else:
                ev.release()
        else:
            mysql.commit()
            data = ex.fetchall()
            ev.release()
            for rec in data:
                host,ts,val = rec
                try:
                    res[host].append([(int(time.mktime(ts.timetuple()))+3*3600)*1000,val])
                except KeyError:
                    res.update(dict([(host,[[(int(time.mktime(ts.timetuple()))+3*3600)*1000,val]])]))
    jq = {}
    for kyi in sorted(res.iterkeys()):
        jq[kyi] = res[kyi]
    if res == {}:
        return json.dumps([0,0])
    else:
        return json.dumps(jq)

def config_saver(chnconf):
    
    
    if chnconf[-1:] == '\n':
        chnconf = chnconf[:-1]
    conffile = open('./data/conf','w')
    conffile.write(chnconf)
    conffile.close()
    open('./data/tr','w').write('1')
        
def config_parser(): #parser for config editor, returns json string
    
    conffile = open('./data/conf','r')
    conflist = []

    for line in conffile:
        if line[-1:] == '\n':
            tmp = line[:-1].split(' = ')
            if tmp[0] == 'admin_mails':
                conflist.append([tmp[0],tmp[1].split(',')])
            else:
                conflist.append(line[:-1].split(' = '))
        else:
            tmp = line.split(' = ')
            if tmp[0] == 'admin_mails':
                conflist.append([tmp[0],tmp[1].split(',')])
            else:
                conflist.append(line.split(' = '))
    return json.dumps(conflist, sort_keys=True)


def web(q):
    run = 1
    serv = BaseHTTPServer.HTTPServer
    httpd = serv((conf.get('ipadr'), int(conf.get('port'))), MyHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    
input = Queue()
webth = Thread(target=web,args=(input,))  
webth.start()

while True:
    #global flag
    flag.wait()
    flag.clear()
    
    ips = []
    input = open('./data/list','r')
    for i in input:
        if i[-1:] == '\n':
            ips.append(i[:-1])
        else:
            ips.append(i)
    num_threads = len(ips)
    if conf.get('debug_lvl') == 'WARN':
        lglvl = logging.WARN
    elif conf.get('debug_lvl') == 'INFO':
        lglvl = logging.INFO
    elif conf.get('debug_lvl') == 'DEBUG':
        lglvl = logging.DEBUG    
    logging.basicConfig(format='[%(levelname)s] %(threadName)s [%(asctime)s] - %(message)s', filename='./'+conf.get('logfile'), level=lglvl)
    
    time.sleep(5)
    
    def mail(ip,tm=None):
        fromaddr = 'From: "Video conference monitoring" <artemav@yandex-team.ru>\r\n'
        toaddrs = 'artemav@yandex-team.ru'
        if tm == None:
            msg = 'Subject: Unit %s down\r\nContent-Type: text/html; charset=utf-8\r\n\r\n\r\nVideoconference unit %s down<br>FQDN: <a href="https://%s">%s</a>\r\n'%(ip,ip,ip,ip)
        else:
            msg = 'Subject: Unit %s down\r\nContent-Type: text/html; charset=utf-8\r\n\r\n\r\nVideoconference unit %s down more than 30 minutes<br>FQDN: <a href="https://%s">%s</a>\r\n'%(ip,ip,ip,ip)
        cc = 'Cc: %s\r\n'%conf.get('admin_mails').replace(',',', ')
        msg = fromaddr+'To: '+toaddrs+'\r\n'+cc+msg
        toaddrs = toaddrs + ', ' + conf.get('admin_mails').replace(',',', ')
        toaddrs = toaddrs.split(', ')
        try:
            server = smtplib.SMTP('outbound-relay.yandex.net:25')
            server.sendmail(fromaddr, toaddrs, msg)
        except Exception:
            logging.error('Can`t send message or connect to server')
        else:
            logging.info('E-mail sent')
    
    def pinger(i, q, o):
        
        
        flag = True
        while flag == True:
            rounds = 0
            ip = q.get()
            if ip != '':
                ret = subprocess.call("ping -c1 %s" % ip,
                                stdout=open('./stdout/'+ip, 'w'),
                                shell=True,
                                stderr=subprocess.STDOUT)
                logging.debug('Threat %s ping %s with res %s'%(i,ip,ret))
                if ret == 0:
                    cn = 0
                    tmp = open('./stdout/'+ip, 'r')
                    for line in tmp:
                        if cn == 0:
                            tmpval = line
                        elif cn == 1:
                            srch0 = re.search('Destination Host Unreachable', line)
                            if srch0 == None:
                                splt = line.split(' ')
                                for j in splt:
                                    if j[0:4] == 'time':
                                        timems = j[5:]
                            #if your ping request in this point - all bad...
                            else:
                                logging.critical('From %s was received "Destination Host Unreachable" answer with "ret=0"'%ip)
                                del(tmpval)
                        elif cn > 1:
                            tmp.close()
                            break
                        cn += 1
                now = datetime.datetime.now()
                try:
                    out = (ip, ret, (int(time.mktime(now.timetuple())+3*3600)*1000), timems)
                except Exception:
                    logging.warn('%s lost package'%ip)
                    out = (ip, ret, (int(time.mktime(now.timetuple())+3*3600)*1000))
                    sql = "INSERT INTO t%s VALUES ('%s', '%s', %s);"%(str(tbl.date()).replace('-',''),ip,now,0.0)
                else:
                    sql = "INSERT INTO t%s VALUES ('%s', '%s', %s);"%(str(tbl.date()).replace('-',''),ip,now,float(timems))
                    del(timems)
                #global ev
                ev.acquire()
                ex.execute(sql)
                mysql.commit()
                ev.release()
                o.put(out)
                q.task_done()
                flag = False
            else:
                rounds = rounds + 1
                if rounds >=10:
                    print 'BZUM'
                    flag = False          
    
    tbl = datetime.datetime.now()
    #global ev
    ev.acquire()
    ex.execute("CREATE TABLE IF NOT EXISTS t%s (host VARCHAR(30), ts TIMESTAMP, val FLOAT(3)) ENGINE MyISAM;"%str(tbl.date()).replace('-',''))
    mysql.commit()
    ev.release()
    for i in range(num_threads):
        logging.debug('Thread %s starting'%i)
        worker = Thread(target=pinger, args=(i, queue, output))
        worker.setDaemon(True)
        worker.start()
    
     
    for ip in ips:
        queue.put(ip) 
    queue.join()
    resultdict = {}
    for x in range(0,len(ips)):    
        res = output.get()
        try:
            resultdict.update(dict([(res[0],[res[2],float(res[3])])]))
        except IndexError:
            resultdict.update(dict([(res[0],[res[2],float(0)])]))
            try:
                failcount.update(dict([(res[0],failcount[res[0]]+1)]))
            except KeyError:
                if res[1] == 1:
                    failcount.update(dict([(res[0],1)]))
            else:
                if failcount[res[0]]>=5:
                    try:
                        delt = datetime.datetime.now()-td[res[0]]
                    except KeyError:
                        now = datetime.datetime.now()
                        logging.warn('%s is unreachable at %s:%s'%(res[0],now.hour,now.minute))
                        if now.hour>=10 and now.hour<22 and now.weekday()<=4:
                            mail(res[0])
                            print 'Standart message'
                        td.update({res[0]:datetime.datetime.now()})
                    else:
                        if delt.seconds>=3600:
                            nw = datetime.datetime.now()
                            logging.warn('%s steal unreachable more than 1 hour at %s:%s'%(res[0],nw.hour,nw.minute))
                            if nw.hour>=10 and nw.hour<22 and nw.weekday()<=4:
                                mail(res[0],1)
                                print 'Not simple message'
                            td.update({res[0]:datetime.datetime.now()}) 
        else:
            try:
                failcount.pop(res[0])
            except Exception:
                pass
            else:
                try:
                    td.pop(res[0])
                except KeyError:
                    pass
    flag.set()
    js = {}
    logging.debug('Dict for json.dumps() before sorting: %s'%resultdict)
    for ky in sorted(resultdict.iterkeys()):
        js[ky] = resultdict[ky]
    logging.debug('Dict for json.dumps() after sorting: %s'%js)
    rl = open('./data/json', 'w')
    rl.write(json.dumps(js,sort_keys=True))
    rl.close()
    tbl_count = sql_tables_show()
    if len(tbl_count) >= conf.get('logdays'):
        sql = 'DROP TABLE %s;'%tbl_count[0]
        ev.acquire()
        ex.execute(sql)
        mysql.commit()
        ev.release()
