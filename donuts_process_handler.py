"""
Process handler for ACP to control Donuts
"""
import os
import time
import signal
import psutil
import threading
import argparse as ap
import subprocess as sp
import Pyro4
import pymysql
from utils import ag_status

# pylint: disable=invalid-name

AG_ON_TIME = 10
AG_OFF_TIME = 30

def argParse():
    """
    Parse the command line args
    """
    p = ap.ArgumentParser()
    p.add_argument('instrument',
                   help='select an instrument',
                   choices=['io', 'callisto', 'europa',
                            'ganymede', 'nites'])
    return p.parse_args()

class Autoguider(object):
    """
    """
    def __init__(self, instrument):
        """
        """
        self.guiding = False
        self.proc = None
        self.instrument = instrument
        self.print_thread = threading.Thread(target=self.printStatus)
        self.print_thread.daemon = True
        self.print_thread.start()

    def printStatus(self):
        """
        display current status
        """
        while True:
            print("Autoguiding: {}".format(self.guiding))
            if self.guiding:
                #self.printLastAgCorrection()
                time.sleep(AG_ON_TIME)
            else:
                time.sleep(AG_OFF_TIME)

    def printLastAgCorrection(self):
        """
        Grab the last autoguider correction
        """
        os.system('cls')
        qry = """
            SELECT *
            FROM autoguider_log_new
            ORDER BY updated DESC
            LIMIT 1
            """
        with pymysql.connect(host='localhost',
                             db='spec_ops',
                             user='speculoos',
                             password='spec_ops',
                             cursorclass=pymysql.cursors.DictCursor) as cur:
            cur.execute(qry)
            result = cur.fetchone()
        if result:
            print('[{}]: {}:'.format(result['updated'],
                                     result['comparison']))
            print('Shifts: X: {:.3f} Y: {:.3f}'.format(result['shift_x'],
                                                       result['shift_y']))
            print('PrePID: X: {:.3f} Y: {:.3f}'.format(result['pre_pid_x'],
                                                       result['pre_pid_y']))
            print('PostPID: X: {:.3f} Y: {:.3f}'.format(result['post_pid_x'],
                                                        result['post_pid_y']))
        else:
            print('No shifts in database')

        print('\nRecent messages:')
        qry2 = """
            SELECT * FROM autoguider_info_log
            ORDER BY message_id DESC
            LIMIT 10
            """
        with pymysql.connect(host='localhost',
                             db='spec_ops',
                             user='speculoos',
                             password='spec_ops',
                             cursorclass=pymysql.cursors.DictCursor) as cur:
            cur.execute(qry2)
            results = cur.fetchall()
        for row in results:
            print("{}: {}".format(row['updated'],
                                  row['message']))

    @Pyro4.expose
    def start_ag(self):
        cmd = "C:\\ProgramData\\Miniconda3\\python.exe " \
              "C:\\Users\\speculoos\\Documents\\GitHub\\DONUTS_ACP\\acp_ag.py {}".format(self.instrument)
        self.proc = sp.Popen(cmd, stdout=sp.PIPE, shell=False, creationflags=sp.CREATE_NEW_PROCESS_GROUP)
        # poll = None means running
        if self.proc.poll() is None:
            self.guiding = True
            print(self.proc.pid)
            return ag_status.success
        elif self.proc.poll() == 0:
            self.guiding = False
            return ag_status.failed
        else:
            self.guiding = False
            return ag_status.unknown

    @Pyro4.expose
    def stop_ag(self):
        if self.proc:
            if self.proc.poll() is None:
                guiding_pid = int(self.proc.pid)
                print('Killing AG script pid={}'.format(self.proc.pid))
                os.kill(self.proc.pid, signal.CTRL_BREAK_EVENT)
                time.sleep(5)
                # get running python processes - check it is dead
                pyproc = [int(p.pid) for p in psutil.process_iter() if 'python' in p.name()]
                if guiding_pid not in pyproc:
                    self.guiding = False
                    self.proc = None
                    return ag_status.success
                else:
                    print('Guiding process {} not dead!'.format(guiding_pid))
                    self.guiding = True
                    return ag_status.failed
        else:
            print('No process to kill')

if __name__ == "__main__":
    args = argParse()
    ag = Autoguider(args.instrument)
    daemon = Pyro4.Daemon(host='localhost', port=9234)
    # uri = PYRO:donuts@localhost:9234
    uri = daemon.register(ag, objectId='donuts')
    print(uri)
    daemon.requestLoop()
