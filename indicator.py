import signal
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3
import os
import subprocess as sp
import thread
import sys
from multiprocessing import Pipe
import signal, psutil
import trello
from trello import TrelloClient
import json
import requests

TRELLO = "/Trello"
ICON = "/resources/app/static/Icon.png"
API_KEY = ''
API_TOKEN = ''


class TrelloIndicator():
    def __init__(self, app_path, boards):
        # paths
        abs_path = os.path.expanduser(app_path)
        self.trello_bin_path = abs_path + TRELLO
        self.trello_icon_path = abs_path + ICON

        # favorite
        self.fav_boards = boards

        # trello client and processes info
        self.trello_client = TrelloClient(api_key=API_KEY,token=API_TOKEN)
        self.parent_conn, self.child_conn = Pipe()
        self.child_proc = None

        # indicator
        indicator = AppIndicator3.Indicator.new(
            self.trello_bin_path, self.trello_icon_path,
            AppIndicator3.IndicatorCategory.OTHER)
        indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)       
        indicator.set_menu(self.create_menu())
        Gtk.main()


    def spawn(self, *args, **kwargs):
        if not self.parent_conn.poll():
            newpid = os.fork()
            if newpid == 0:
                # shild process
                self.child_conn.send('on')
                sp.call(self.trello_bin_path)
                self.parent_conn.recv()
                sys.exit(0)
            else:
                # parent process
                parent = psutil.Process(newpid)
                children = []
                while not children:
                    children = parent.children()

                assert len(children) == 1, "Too many children.. this was not expected"
                self.child_proc = children[0]

        else:
            # process is opened already, give it the focus
            p = sp.Popen(["wmctrl -lp"], stderr=sp.PIPE, stdout=sp.PIPE, shell=True)
            w_list, _  = p.communicate()
            line = [l for l in w_list.split('\n') if str(self.child_proc.pid) in l]
            assert len(line) == 1, "Too many processes have been spawned.. something is wrong"
            wmctrl_fields = [x for x in line[0].split(' ') if x]
            name_proc = ' '.join(wmctrl_fields[4:])
            sp.call("wmctrl -a \"" + name_proc + "\"", shell=True)

    def blank_fn(self, *args, **kwargs):
        pass

    def add_boards(self, menu):
        # boards
        # TODO check connection
        #show = Gtk.MenuItem('Can\'t retrieve boards right now')
        #show.connect('activate', self.blank_fn)
        #show.set_sensitive(False)
        #menu.append(show)

        remote_boards = self.trello_client.list_boards()
        for board_name, list_name in self.fav_boards:
            entry = Gtk.MenuItem(list_name)
            entry.connect('activate', self.blank_fn)
            entry.set_sensitive(False)
            menu.append(entry)

            remote_board = [b for b in remote_boards if b.name == board_name][0]
            my_list = [l for l in remote_board.list_lists() if l.name == list_name][0]
            cards = my_list.list_cards()
            print cards
            for card in cards:
                entry = Gtk.MenuItem(card.name)
                entry.connect('activate', self.blank_fn)
                menu.append(entry)
            # separator
            menu_sep = Gtk.SeparatorMenuItem()
            menu.append(menu_sep)

    def populate_menu(self, *args, **kwargs):
        menu = Gtk.Menu()

        self.add_boards(menu)

        # separator
        menu_sep = Gtk.SeparatorMenuItem()
        menu.append(menu_sep)

        # show/update buttons
        pop_menu = Gtk.MenuItem('Update')
        pop_menu.connect('activate', self.populate_menu)
        menu.append(pop_menu)

        show = Gtk.MenuItem('Show')
        show.connect('activate', self.spawn)
        menu.append(show)

        # separator
        menu_sep = Gtk.SeparatorMenuItem()
        menu.append(menu_sep)

        # quit
        item_quit = Gtk.MenuItem('Quit')
        item_quit.connect('activate', self.stop)
        menu.append(item_quit)

        menu.show_all()
        return menu

    def create_menu(self):
        return self.populate_menu()

    def stop(self, source):
        Gtk.main_quit()
        self.child.send_signal(signal.SIGTERM)
        sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    if len(sys.argv) < 2:
        print "Usage: " + sys.argv[0] + " config file"
        sys.exit(0)

    with open(sys.argv[1], 'r') as fp:
        config = json.load(fp)
        TrelloIndicator(config['path'], config['boards']).create_menu()
