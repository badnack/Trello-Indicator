import signal
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3
import signal
import os
import subprocess as sp
import thread
import sys
from multiprocessing import Process, Pipe
import signal, psutil


TRELLO = "/Trello"
ICON = "/resources/app/static/Icon.png"

class Indicator():
    def __init__(self):
        if len(sys.argv) < 2:
            print "Usage: " + sys.argv[0] + " trello_client_path"
            sys.exit(0)

        abs_path = os.path.expanduser(sys.argv[1])
        self.trello_bin_path = abs_path + TRELLO
        self.trello_icon_path = abs_path + ICON

        indicator = AppIndicator3.Indicator.new(
            self.trello_bin_path, self.trello_icon_path,
            AppIndicator3.IndicatorCategory.OTHER)
        indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)       
        indicator.set_menu(self.create_menu())
        self.parent_conn, self.child_conn = Pipe()
        self.child = None
        self.spawn()
        Gtk.main()

    def spawn(self, *args, **kwargs):
        if not self.parent_conn.poll():
            newpid = os.fork()
            if newpid == 0:
                self.child_conn.send('runnig')
                sp.call(self.trello_bin_path)
                self.parent_conn.recv()
                sys.exit(0)
            else:
                # parent process
                try:
                    parent = psutil.Process(newpid)
                except psutil.NoSuchProcess:
                    return

                children = []
                while not children:
                    children = parent.children()

                assert len(children) == 1, "Too many children.. this was not expected"
                self.child = children[0]

        else:
            # process is opened already, give the focus to it
            p = sp.Popen(["wmctrl -lp"], stderr=sp.PIPE, stdout=sp.PIPE, shell=True)
            w_list, _  = p.communicate()
            line = [l for l in w_list.split('\n') if str(self.child.pid) in l]
            assert len(line) == 1, "Too many processes have been spawned.. something is wrong"
            wmctrl_fields = [x for x in line[0].split(' ') if x]
            name_proc = ' '.join(wmctrl_fields[4:])
            sp.call("wmctrl -a \"" + name_proc + "\"", shell=True)
            
    def create_menu(self):
        menu = Gtk.Menu()
        show = Gtk.MenuItem('Show')
        show.connect('activate', self.spawn)
        menu.append(show)
        menu_sep = Gtk.SeparatorMenuItem()
        menu.append(menu_sep)
        item_quit = Gtk.MenuItem('Quit')
        item_quit.connect('activate', self.stop)
        menu.append(item_quit)

        menu.show_all()
        return menu

    def stop(self, source):
        Gtk.main_quit()
        self.child.send_signal(signal.SIGTERM)
        sys.exit(0)
        
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Indicator().create_menu()
