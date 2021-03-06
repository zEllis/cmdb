import os,time,commands,json
from salt.client import LocalClient
from www.models import *
from celery.task import task
from asset.utils import logs,dingding_robo






class wwwFun:
    def __init__(self,env,username,ip,fileName,phone_number):
        self.env = env
        self.username = username
        self.ip = ip
        self.fileName = fileName
        self.f = open(self.fileName,'w')
        self.result = []
        self.phone_number = phone_number




    def __nginx_backup(self,proxy_server,web_server,nginx_module,deploy_pillar):
        self.proxy_server = proxy_server
        self.web_server = web_server
        self.nginx_module = nginx_module
        self.deploy_pillar = deploy_pillar

        try:  ##########nginx backup#######

            s, backup = commands.getstatusoutput("salt " + self.proxy_server + " state.sls queue=True " + self.nginx_module + " " + self.deploy_pillar)
            self.f.write(backup)
            self.f.flush()
            self.result.append(backup)

            if backup.find('Failed:     0') < 0:
                print "!!!!!!!!!!!!!!!!!! [backup server] ERROR !!!!!!!!!!!!!!!!!!!"
                return 1
            self.f.write('\n\n\n\n\n')
            return 0
        except Exception, e:
            print e
            self.f.write('error')
            self.f.close()
            dingding_robo(self.web_server, self.site, 'error', self.username, self.phone_number)
            logs(self.username, self.ip, self.site, 'Failed')
            return 1




    def __svn_update(self,web_server,svn_path,svn_username,svn_password,svn_revision):
        self.web_server = web_server
        self.svn_path = svn_path
        self.svn_username = svn_username
        self.svn_password = svn_password
        self.svn_revision = svn_revision


        try:  #####svn update########
            update_cmd = '\'svn update -r %s %s --username=%s --password=%s \'' % (self.svn_revision,self.svn_path, self.svn_username, self.svn_password)
            s, update = commands.getstatusoutput("salt " + self.web_server + " cmd.run " + update_cmd)
            self.f.write(update)
            self.f.flush()
            self.result.append(update)

            if update.find('Error') > 0 or update.find('error') > 0:
                print "!!!!!!!!!!!!!!!!!! [update svn] ERROR !!!!!!!!!!!!!!!!!!!"
                return 1
            self.f.write('\n\n\n\n\n')
            return 0
        except Exception, e:
            print e
            self.f.write('error')
            self.f.close()
            dingding_robo(self.web_server, self.site, 'error', self.username, self.phone_number)
            logs(self.username, self.ip, self.site, 'Failed')
            return 1




    def __iis_recycle(self,web_server,recycle_cmd,web_url,action):
        self.web_server = web_server
        self.recycle_cmd = recycle_cmd
        self.web_url = web_url
        self.action = action


        try:  ####recycle iis#######
            s, recycle = commands.getstatusoutput("salt " + self.web_server + " cmd.run '" + self.recycle_cmd + "'")
            self.f.write(recycle)
            self.f.flush()
            self.result.append(recycle)

            if recycle.find('Fail') > 0 or recycle.find('fail') > 0:
                print "!!!!!!!!!!!!!!!!!! [recycle iis] ERROR !!!!!!!!!!!!!!!!!!"
                return 1
            self.f.write('\n\n\n\n\n')



            i = 0
            while i < 5:
                start_time = time.time()
                s, testUrl = commands.getstatusoutput("curl -H \"Host:" + self.site + "\" -I " + self.web_url)
                self.f.write(testUrl)
                self.f.flush()
                self.f.write('\n\n\n\n\n')
                print time.time() - start_time
                if time.time() - start_time < 2:
                    break
                i = i + 1
            if i == 5:
                print "!!!!!!!!!!!!!!!!!! [recycle iis] TIMEOUT !!!!!!!!!!!!!!!!!!"
                self.f.write('error')
                self.f.close()
                return 1
            if self.action == 'recycle':
                dingding_robo(self.web_server, 'recycle ' + self.site, 'success', self.username, self.phone_number)
            elif self.action == 'revert':
                dingding_robo(self.web_server, 'revert ' + self.site, 'success', self.username, self.phone_number)
            else:
                dingding_robo(self.web_server,self.site, 'success', self.username, self.phone_number)
            return 0
        except Exception, e:
            print e
            self.f.write('error')
            self.f.close()
            if self.action == 'recycle':
                dingding_robo(self.web_server,self.site, 'error', self.username,self.phone_number)
            elif self.action == 'revert':
                dingding_robo(self.web_server,self.site, 'error', self.username,self.phone_number)
            else:
                dingding_robo(self.web_server,self.site, 'error', self.username,self.phone_number)
            logs(self.username, self.ip, self.site, 'Failed')
            return 1






    def deploy(self,site,action='svn',revision='HEAD'):

        self.site = site
        self.action = action
        self.revision = revision
        obj = webSite.objects.filter(env=self.env).filter(webSite=self.site)



        for info in obj:
            for host in info.checkUrl.values():
                print host['host']
                for m in info.state_module.values():
                    deploy_pillar = "pillar=\"{'deployserver':'" + host['host'] + "', 'deployhost':'" + info.salt_pillar_host + "'}\""
                    nginx_backup = self.__nginx_backup(info.lb_server,host['host'],m['state_module'],deploy_pillar)
                    if nginx_backup == 1:
                        self.f.write('error')
                        exit()
                if self.action in ['svn','revert']:
                    svn_up = self.__svn_update(host['host'],info.svn_path,info.svn_username,info.svn_password,self.revision)
                    if svn_up == 1:
                        self.f.write('error')
                        exit()
                elif self.action == 'recycle':
                    pass

                recycle = self.__iis_recycle(host['host'],info.recycle_cmd,host['url'],self.action)
                if recycle == 1:
                    self.f.write('error')
                    exit()


            for m in info.state_module.values():    ######nginx all online########
                print m['state_module']
                deploy_pillar = "pillar=\"{'deployserver':'none', 'deployhost':'none'}\""
                status = self.__nginx_backup(info.lb_server,host['host'],m['state_module'],deploy_pillar)

                if status == 1:
                    logs(self.username, self.ip, self.site, 'Failed')
                    self.f.write('error')
                    exit()


        self.f.write('done')
        self.f.flush()
        self.f.close()
        logs(self.username, self.ip, self.site, 'Successful')


        return self.result







@task
def deployWww(env,site,username,ip,fileName,phone_number):
    obj = wwwFun(env,username,ip,fileName,phone_number)
    obj.deploy(site,'svn')



@task
def deployWwwRecycle(env,site,username,ip,fileName,phone_number):
    obj = wwwFun(env,username,ip,fileName,phone_number)
    obj.deploy(site,'recycle')


@task
def deployWwwRevert(env,site,username,ip,fileName,reversion,phone_number):
    obj = wwwFun(env,username,ip,fileName,phone_number)
    obj.deploy(site,'revert',reversion)
