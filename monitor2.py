from threading import Thread, Event
import subprocess, time, datetime, BaseHTTPServer, MySQLdb, SimpleHTTPServer, re, ssl, json, smtplib, logging, warnings
from Queue import Queue

#kostil' dergaet mysql glupim zaprosom, chtobi ne padal po Mysql gone away
def kostil():
    ev.wait()
    ev.clear()
    try:
        ex.execute("SHOW TABLES;")
    except Exception:
        print 'except str 118'
    else:
        mysql.commit()
    ev.set()

def config():
    
    conffile = open('./data/conf','r')
    conflist = []
    confdict = {}
    
    for line in conffile:
        if line[-1:] == '\n':
            conflist.append(re.split('\s*=\s*', line[:-1]))
        else:
            conflist.append(re.split('\s*=\s*',line))    
    
    for k,v in conflist:
        confdict.update({k:v})
    return confdict

def web(q):
    httpd = BaseHTTPServer.HTTPServer((conf.get('ipadr'), int(conf.get('port'))), MyHandler)
    httpd.socket = ssl.wrap_socket(httpd.socket, certfile='./data/sslcert.pem', server_side=True)
    httpd.serve_forever()

def pinger(i, q, o):
    flag = True
    while flag == True:
        ip = q.get()
        if ip != '':
            ret = subprocess.call("ping -c1 -W1 %s" % ip, stdout=open('/dev/null', 'w'), shell=True, stderr=subprocess.STDOUT)
            out = (ip, ret, datetime.datetime.now())
            o.put(out)
            q.task_done()
            flag = False

def mail(ip,tm=None):
        fromaddr = 'From: "Video conference monitoring" <artemav@yandex-team.ru>\r\n'
        toaddrs = 'artemav@yandex-team.ru'
        if tm == None:
            msg = 'Subject: Unit %s down\r\nContent-Type: text/html; charset=utf-8\r\n\r\n\r\nVideoconference unit %s down<br>FQDN: <a href="https://%s">%s</a>\r\n'%(ip,ip,ip,ip)
        else:
            msg = 'Subject: Unit %s down\r\nContent-Type: text/html; charset=utf-8\r\n\r\n\r\nVideoconference unit %s down more than 1 hour<br>FQDN: <a href="https://%s">%s</a>\r\n'%(ip,ip,ip,ip)
        cc = 'Cc: %s\r\n'%conf.get('admin_mails').replace(',',', ')
        msg = fromaddr+'To: '+toaddrs+'\r\n'+cc+msg
        toaddrs = toaddrs + ', ' + conf.get('admin_mails').replace(',',', ')
        toaddrs = toaddrs.split(', ')
        try:
            server = smtplib.SMTP('outbound-relay.yandex.net:25')
            server.sendmail(fromaddr, toaddrs, msg)
        except Exception:
            print 'Can`t send message or connect to server'
        else:
            print 'E-mail sent'

class MyHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_GET(self):
        if re.search('/$', self.path) != None:
            self.response(open('./data/pages/monitor','r').read())
        elif re.search('.js$', self.path) != None:
            self.response(open('./data/plugins'+self.path,'r').read(), 200, 'text/javascript')
        elif re.search('.css$', self.path) != None:
            self.response(open('./data/css'+self.path, 'r').read(), 200, 'text/css')
        elif re.search('getstate', self.path) != None:
            self.response(self.sql_get(self.sql_tables_show()))
        elif re.search('.png$', self.path) != None:
            self.response(open('./data/img'+self.path, 'r').read(), 200, 'image/png')
        elif re.search('hostlistget', self.path) != None:
            self.response(json.dumps(open('./data/list','r').read().split('\n')), 200, 'application/json')
        elif re.search('listeditor', self.path) != None:
            self.response(open('./data/pages/listedit','r').read())
        elif re.search('configet', self.path) != None:
            self.response(self.config_parser(), 200, 'application/json')
        elif re.search('config', self.path) != None:
            self.response(open('./data/pages/config','r').read())
        else:
            self.response('Error', 404)
            
    def do_POST(self):
        if self.path == '/updatelist':
            content_len = int(self.headers.getheader('content-length', 0))
            post_body = json.loads(self.rfile.read(content_len))
            open('./data/list','w').write('\n'.join(post_body))
            open('./data/tr','w').write('1')
            self.response('Done')
        elif self.path == '/deletel':
            content_len = int(self.headers.getheader('content-length', 0))
            post_body = self.rfile.read(content_len)
            sql = 'DROP TABLE %s;'%(post_body.replace('-','_').replace('.','_'))
            ev.wait()
            ev.clear()
            try:
                ex.execute(sql)
            except Exception:
                print 'except str 94'
            else:
                mysql.commit()
            ev.set()
            self.response('Done')
        elif self.path == '/updateconfig':
            content_len = int(self.headers.getheader('content-length', 0))
            post_body = json.loads(self.rfile.read(content_len))
            self.config_saver(post_body)
            self.response('Done')
            
    def response(self, cont, resp=200, type='text/html'):
        self.send_response(resp)
        self.send_header("Content-type", type)
        self.end_headers()
        self.wfile.write(cont)
        
    def sql_tables_show(self):
        ev.wait()
        ev.clear()
        resu = []
        try:
            ex.execute("SHOW TABLES;")
        except Exception:
            print 'except str 118'
        else:
            mysql.commit()
            tables = ex.fetchall()
            for rec in tables:
                resu.append(rec[0])
        ev.set()
        return resu
        
    def sql_get(self,tables):
        resu = {}
        ev.wait()
        ev.clear()
        for tbl in tables:
            sql = 'SELECT * FROM %s ORDER BY id DESC LIMIT 1'%tbl
            try:
                ex.execute(sql)
            except Exception:
                print 'except str 137'
            else:
                mysql.commit()
                tmpres = ex.fetchall()
                elem = re.sub('_yndx_net','.yndx.net',tbl).replace('_','-')
                resu[elem] = [(time.mktime(tmpres[0][1].timetuple()))*1000,tmpres[0][2]]
        ev.set()
        js = {}
        for ky in sorted(resu.iterkeys()):
            js[ky] = resu[ky]
        return json.dumps(js)
    
    def config_parser(self): #parser for config editor, returns json string
    
        conffile = open('./data/conf','r')
        conflist = {}
    
        for line in conffile:
            if line[-1:] == '\n':
                tmp = line[:-1].split(' = ')
                if tmp[0] == 'admin_mails':
                    conflist.update({tmp[0] : tmp[1].split(',')})
                else:
                    conflist.update( { line[:-1].split(' = ')[0] : line[:-1].split(' = ')[1] })
            else:
                tmp = line.split(' = ')
                if tmp[0] == 'admin_mails':
                    conflist.update({ tmp[0] : tmp[1].split(',') })
                else:
                    conflist.update( { line.split(' = ')[0] : line.split(' = ')[1] } )
        return json.dumps(conflist, sort_keys=True)
    
    def config_saver(self,confobj):
        result = ''
        for (k,v) in confobj.items():
            if k == 'admin_mails':
                v = ','.join(v)
                result = result + '%s = %s\n'%(k,v)
            else:
                result = result + '%s = %s\n'%(k,v)
        if result[-1:] == '\n':
            result = result[:-1]
        open('./data/conf','w').write(result)
        open('./data/tr','w').write('1')
    
    def log_message(self, format, *args):
        logstr = '[%s] - %s %s\n'%(self.log_date_time_string(),self.address_string(),format%args)
        logging.info(logstr)

#load config
conf = config()
if conf.get('debug_lvl') == 'WARN':
    lglvl = logging.WARN
elif conf.get('debug_lvl') == 'INFO':
    lglvl = logging.INFO
elif conf.get('debug_lvl') == 'DEBUG':
    lglvl = logging.DEBUG    
logging.basicConfig(format='[%(levelname)s] [%(asctime)s] - %(message)s', filename='./'+conf.get('logfile'), level=lglvl)

#get ips from file
ips = []
input = open('./data/list','r')
for i in input:
    if i[-1:] == '\n':
        ips.append(i[:-1])
    else:
        ips.append(i)
        
#set thread limit
num_threads = len(ips)

#creating event flag
global ev
ev = Event()
ev.set()

#creating input and output queues
queue = Queue()
output = Queue()

#set mysql variables
global mysql, ex
mysql = MySQLdb.connect(host='localhost', user=conf.get('db_login'), passwd=conf.get('db_password'), db=conf.get('database'))
ex = mysql.cursor()
warnings.simplefilter('ignore')

#creating new table
ev.wait()
ev.clear()
for host in ips:
    ex.execute("CREATE TABLE IF NOT EXISTS %s (id MEDIUMINT NOT NULL AUTO_INCREMENT, ts TIMESTAMP, state BOOLEAN, PRIMARY KEY (id)) ENGINE MyISAM;"%(host.replace('-','_')).replace('.','_'))
mysql.commit()
ev.set()

#counter of failed ping
failcount = {}

#last send mail counter
ms = {}

#availablity write flag
awflag = {}
for ip in ips:
    awflag.update(dict([(ip, False)]))

#web thread spawn
input = Queue()
webth = Thread(target=web,args=(input,))  
webth.start()

#main loop
while True:
    
    #spawning pinger threads            
    for i in range(num_threads):
        worker = Thread(target=pinger, args=(i, queue, output))
        worker.setDaemon(True)
        worker.start()
    
    #put IPs to queue
    for ip in ips:
        queue.put(ip)
        queue.join()
    
    #analizing output
    for x in range(0,len(ips)):    
        res = output.get()
        if res[1] == 1:
            try:
                failcount.update(dict([(res[0],failcount[res[0]]+1)]))
            except KeyError:
                failcount.update(dict([(res[0],1)]))
            else:
                if failcount[res[0]] == 2:
                    print 'second'
                    sql = "INSERT INTO %s (ts, state) VALUES ('%s', 0);"%((res[0].replace('-','_')).replace('.','_'),res[2])
                    ev.wait()
                    ev.clear()
                    try:
                        ex.execute(sql)
                    except Exception:
                        print 'except str 279'
                    else:
                        mysql.commit()
                    ev.set()
                    awflag[res[0]] == False
                elif failcount[res[0]] >= 6:
                    try:
                        delt = datetime.datetime.now()-ms[res[0]]
                    except KeyError:
                        now = datetime.datetime.now()
                        if now.hour>=10 and now.hour<22 and now.weekday()<=4:
                            mail(res[0])
                        ms.update({res[0]:datetime.datetime.now()})
                    else:
                        if delt.seconds>=3600:
                            nw = datetime.datetime.now()
                            if nw.hour>=10 and nw.hour<22 and nw.weekday()<=4:
                                mail(res[0],1)
                            ms.update({res[0]:datetime.datetime.now()}) 
        elif res[1] == 0:
            if awflag[res[0]] == False:
                sql = "INSERT INTO %s (ts, state) VALUES ('%s', 1);"%((res[0].replace('-','_')).replace('.','_'),res[2])
                ev.wait()
                ev.clear()
                try:
                    ex.execute(sql)
                except Exception:
                    print 'except str 307'
                else:
                    mysql.commit()
                ev.set()
                awflag[res[0]] = True
            try:
                failcount.pop(res[0])
            except Exception:
                pass
            else:
                try:
                    ms.pop(res[0])
                except Exception:
                    pass
                awflag[res[0]] = False
    time.sleep(5)
    kostil()
    