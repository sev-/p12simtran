#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# romiq.kh@gmail.com, 2014

import sys, os
import tkinter
from tkinter import ttk, font, filedialog, messagebox
from idlelib.WidgetRedirector import WidgetRedirector
import traceback
import urllib.parse
import math

# Image processing
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

# Translations
try:
    import polib
except ImportError:
    polib = None

import petka

APPNAME = "P1&2 Explorer"
VERSION = "v0.3g 2014-12-27"

def hlesc(value):
    if value is None:
        return "None"
    return value.replace("\\", "\\\\").replace("<", "\\<").replace(">", "\\>")

def cesc(value):
    return value.replace("\\", "\\\\").replace("\"", "\\\"")

def fmt_hl(loc, desc):
    return "<a href=\"{}\">{}</a>".format(loc, desc)

def fmt_hl_len(loc, desc, ln):
    sz = max(ln - len(desc), 0)
    return " "*sz + fmt_hl(loc, desc)

def fmt_arg(value):
    if value < 10:
        return "{}".format(value)
    elif value == 0xffff:
        return "-1"
    else:
        return "0x{:X}".format(value)
    
def fmt_dec(value, add = 0):
    return "{{:{}}}".format(fmt_dec_len(value, add))
        
def fmt_dec_len(value, add = 0):
    if value == 0:
        d = 1
    else:
        d = int(math.log10(value)) + 1
    d += add
    return d
    
def translit(text):
    ru = "абвгдеёзийклмнопрстуфхъыьэАБВГДЕЁЗИЙКЛМНОПРСТУФХЪЫЬЭ"
    en = "abvgdeezijklmnoprstufh'y'eABVGDEEZIJKLMNOPRSTUFH'Y'E"
    sl = {
        "ж": "zh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ю": "yu",
        "я": "ya",
        "Ж": "Zh",
        "Ц": "Ts",
        "Ч": "Ch",
        "Ш": "Sh",
        "Щ": "Sch",
        "Ю": "Yu",
        "Я": "Ya"
    }
    ret = ""
    allcaps = True
    for ch in text:
        ps = ru.find(ch)
        if ps >= 0:
            ret += en[ps]
        elif ch in sl:
            ret += sl[ch]
        else:
            ret += ch
        allcaps = (allcaps and ch.upper() == ch)
    if allcaps:
        ret = ret.upper()
    return ret
    
# thanx to http://effbot.org/zone/tkinter-text-hyperlink.htm
class HyperlinkManager:
    def __init__(self, text):
        self.text = text
        self.text.tag_config("hyper", foreground = "blue", underline = 1)
        self.text.tag_bind("hyper", "<Enter>", self._enter)
        self.text.tag_bind("hyper", "<Leave>", self._leave)
        self.text.tag_bind("hyper", "<Button-1>", self._click)
        bold_font = font.Font(text, self.text.cget("font"))
        bold_font.configure(weight = "bold")
        self.text.tag_config("bold", font = bold_font)
        italic_font = font.Font(text, self.text.cget("font"))
        italic_font.configure(slant = "italic")
        self.text.tag_config("italic", font = italic_font)
        self.text.tag_config("underline", underline = 1)
        self.reset()

    def reset(self):
    	self.links = {}
    	self.colors = []
    	self.bgs = []

    def add(self, action):
        # add an action to the manager.  returns tags to use in
        # associated text widget
        tag = "hyper-{}".format(len(self.links))
        self.links[tag] = action
        return "hyper", tag

    def color(self, color):
        tag = "color-{}".format(color)
        if tag not in self.colors:
            self.colors.append(tag)
            self.text.tag_config(tag, foreground = color)
            self.text.tag_raise("hyper")
        return (tag,)

    def bg(self, color):
        tag = "bg-{}".format(color)
        if tag not in self.bgs:
            self.bgs.append(tag)
            self.text.tag_config(tag, background = color)
            self.text.tag_raise("hyper")
        return (tag,)

    def _enter(self, event):
        self.text.config(cursor = "hand2")

    def _leave(self, event):
        self.text.config(cursor = "")

    def _click(self, event):
        for tag in self.text.tag_names(tkinter.CURRENT):
            if tag[:6] == "hyper-":
                self.links[tag]()
                return

# thanx http://tkinter.unpythonic.net/wiki/ReadOnlyText
class ReadOnlyText(tkinter.Text):
    def __init__(self, *args, **kwargs):
        tkinter.Text.__init__(self, *args, **kwargs)
        self.redirector = WidgetRedirector(self)
        self.insert = \
            self.redirector.register("insert", lambda *args, **kw: "break")
        self.delete = \
            self.redirector.register("delete", lambda *args, **kw: "break")

class App(tkinter.Frame):
    def __init__(self, master):
        tkinter.Frame.__init__(self, master)
        master.title(APPNAME)
        self.pack(fill = tkinter.BOTH, expand = 1)
        self.pad = None
        self.clear_data()
        # path
        if hasattr(sys, 'frozen'):
            self.app_path = sys.executable
        else:
            self.app_path = __file__
        self.app_path = os.path.abspath(os.path.dirname(self.app_path))
        self.start_act = []
        # gui
        self.path_handler = {}
        self.curr_main = -1 # 0 - frame, 1 - canvas
        self.curr_path = []
        self.curr_help = ""
        self.last_path = [None]
        self.last_fn = ""
        self.curr_gui = []
        self.curr_state = {} # local state for location group
        self.curr_lb_acts = None
        self.curr_lb_idx = None
        self.hist = []
        self.histf = []
        self.gl_state = {} # global state until program exit
        # canvas
        self.need_update = False
        self.canv_view_fact = 1
        self.main_image = tkinter.PhotoImage(width = 1, height = 1)
        # add on_load handler
        self.after_idle(self.on_first_display)
        
    def clear_data(self):
        self.sim = None
        # store manager
        self.strfm = None
        # save
        self.save = None
        # translation
        self.tran = None
           
    def create_widgets(self):
        ttk.Style().configure("Tool.TButton", width = -1) # minimal width
        ttk.Style().configure("TLabel", padding = self.pad)
        ttk.Style().configure('Info.TFrame', background = 'white', \
            foreground = "black")

        # toolbar
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(fill = tkinter.BOTH)
        btns = [
            ["Outline", lambda: self.open_path("")],
            ["Help", self.on_help],
            [None, None],
            ["<-", self.on_back],
            ["->", self.on_forward],
        ]
        for text, cmd in btns:
            if text is None:
                frm = ttk.Frame(self.toolbar, width = self.pad, 
                    height = self.pad)
                frm.pack(side = tkinter.LEFT)
                continue            
            btn = ttk.Button(self.toolbar, text = text, \
                style = "Tool.TButton", command = cmd)
            btn.pack(side = tkinter.LEFT)
        frm = ttk.Frame(self.toolbar, width = self.pad, height = self.pad)
        frm.pack(side = tkinter.LEFT)
        
        # main panel
        self.pan_main = ttk.PanedWindow(self, orient = tkinter.HORIZONTAL)
        self.pan_main.pack(fill = tkinter.BOTH, expand = 1)
        
        # leftpanel
        self.frm_left = ttk.Frame(self.pan_main)
        self.pan_main.add(self.frm_left)
        # main view
        self.frm_view = ttk.Frame(self.pan_main)
        self.pan_main.add(self.frm_view)
        self.frm_view.grid_rowconfigure(0, weight = 1)
        self.frm_view.grid_columnconfigure(0, weight = 1)
        self.scr_view_x = ttk.Scrollbar(self.frm_view, 
            orient = tkinter.HORIZONTAL)
        self.scr_view_x.grid(row = 1, column = 0, \
            sticky = tkinter.E + tkinter.W)
        self.scr_view_y = ttk.Scrollbar(self.frm_view)
        self.scr_view_y.grid(row = 0, column = 1, sticky = \
            tkinter.N + tkinter.S)
        # canvas
        self.canv_view = tkinter.Canvas(self.frm_view, height = 150, 
            bd = 0, highlightthickness = 0, 
            scrollregion = (0, 0, 50, 50),
            )
        # don't forget
        #   canvas.config(scrollregion=(left, top, right, bottom))
        self.canv_view.bind('<Configure>', self.on_resize_view)
        self.canv_view.bind('<ButtonPress-1>', self.on_mouse_view)
        
        # text
        self.text_view = ReadOnlyText(self.frm_view,
            highlightthickness = 0,
            )
        self.text_hl = HyperlinkManager(self.text_view)
        self.text_view.bind('<Configure>', self.on_resize_view)
        
        
        def desc_def(aname, name, lst = {}):
            def desc(path):
                if len(path) > 1:
                    return "{} {}".format(name, lst.get(path[1], 
                        "#{}".format(path[1])))
                else:
                    return aname
            return desc
        
        # bind path handlers
        self.path_handler["parts"] = [self.path_parts, self.desc_parts]
        self.path_handler["res"] = [self.path_res, self.desc_res]
        self.path_handler["objs"] = [self.path_objs_scenes,
            desc_def("Objects", "Object")]
        self.path_handler["scenes"] = [self.path_objs_scenes,
            desc_def("Scenes", "Scene")]
        self.path_handler["names"] = [self.path_names,
            desc_def("Names", "Name")]
        self.path_handler["invntr"] = [self.path_invntr,
            desc_def("Invntrs", "Invntr")]
        self.path_handler["msgs"] = [self.path_msgs,
            desc_def("Messages", "Message")]
        self.path_handler["dlgs"] = [self.path_dlgs,
            desc_def("Dialog groups", "Dialog group")]
        self.path_handler["casts"] = [self.path_casts,
            desc_def("Casts", "Cast")]
        self.path_handler["opcodes"] = [self.path_opcodes,
            desc_def("Opcodes", "Opcode", 
            {k:v[0] for k, v in petka.engine.OPCODES.items()})]
        self.path_handler["dlgops"] = [self.path_dlgops,
            desc_def("Dialog opcodes", "Dialog opcode",
            {k:v[0] for k, v in petka.engine.DLGOPS.items()})]
        self.path_handler["strs"] = [self.path_stores,
            desc_def("Stores", "Store")]
        self.path_handler["files"] = [self.path_files, self.desc_files]
        self.path_handler["save"] = [self.path_save, "Save"]
        self.path_handler["test"] = [self.path_test, "Tests"]
        self.path_handler["about"] = [self.path_about, "About"]
        self.path_handler["support"] = [self.path_support, "Support"]
        self.path_handler["help"] = [self.path_help, self.desc_help]
        self.path_handler["info"] = [self.path_info, "Information"]

        self.update_after()
        repath = "/about"
        for cmd, arg in self.start_act:
            if cmd == "load":
                if not self.open_data_from(arg):
                    repath = ""
                    break
            elif cmd == "str":
                if not self.open_str_from(arg):
                    repath = ""
                    break
                else:
                    repath = "/strs"
            elif cmd == "savedat":
                if not self.open_savedat_from(arg):
                    repath = ""
                    break
                else:
                    repath = "/save"
            elif cmd == "tran":
                if not self.open_tran_from(arg):
                    repath = ""
                    break
            elif cmd == "open":
                repath = ""
                if not self.open_path(arg):
                    print("DEBUG: stop opening after " + arg)
                    repath = ""
                    break
        if repath:
            self.open_path(repath)

    def create_menu(self):
        def mkmenupaths(parent, items):                
            for n in items:
                if n is None:
                    parent.add_separator()
                else:
                    def cmd(n):
                        return lambda: self.open_path(n)
                    parent.add_command(
                            command = cmd(n),
                            label = self.desc_path(n))

        self.menubar = tkinter.Menu(self.master)
        self.master.configure(menu = self.menubar)

        self.menufile = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menufile,
                label = "File")
        self.menufile.add_command(
                command = self.on_open_data,
                label = "Open data...")
        self.menufile.add_command(
                command = self.on_open_savedat,
                label = "Open SAVEx.DAT...")
        self.menufile.add_separator()
        self.menufile.add_command(
                command = self.on_open_str,
                label = "Open STR...")
        self.menufile.add_separator()
        self.menufile.add_command(
                command = self.on_exit,
                label = "Quit")    

        self.menuedit = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menuedit,
                label = "Edit")
                
        editnav = ["/parts", None, "/res", "/objs", "/scenes", "/names", 
            "/invntr", "/casts", "/msgs", "/dlgs", "/opcodes", "/dlgops", 
            "/strs", "/files", "/save"]
        mkmenupaths(self.menuedit, editnav)
        
        self.menunav = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menunav,
                label = "Navigation")
        self.menunav.add_command(
                command = self.on_back,
                label = "Back")
        self.menunav.add_command(
                command = self.on_forward,
                label = "Forward")
        self.menunav.add_separator()
        self.menunav.add_command(
                command = lambda: self.open_path(""),
                label = "Outline")
        self.menunav.add_separator()
        self.menunav.add_command(
                command = self.show_hist, label = "History")

        if polib:
            menutran = tkinter.Menu(self.menubar, tearoff = 0)
            self.menubar.add_cascade(menu = menutran,
                    label = "Translation")
            menutran.add_command(
                    command = self.on_tran_save,
                    label = "Save template (.pot)")
            menutran.add_command(
                    command = self.on_tran_save_tlt,
                    label = "Save transliterate template (.pot)")
            menutran.add_command(
                    command = self.on_tran_load,
                    label = "Load translation (.po)")
            menutran.add_separator()
            menutran.add_command(
                    command = self.on_tran_save_lod,
                    label = "Save DIALOGUE.LOD")
            menutran.add_command(
                    command = self.on_tran_save_names,
                    label = "Save NAMES.INI")

        self.menuhelp = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menuhelp,
                label = "Help")
        helpnav = ["/help/index", None, "/support", "/info", "/about"]
        mkmenupaths(self.menuhelp, helpnav)

    def update_after(self):
        if not self.need_update:
            self.after_idle(self.on_idle)
            self.need_update = True

    def on_idle(self):
        self.need_update = False
        self.update_canvas()

    def on_first_display(self):
        fnt = font.Font()
        try:
            self.pad = fnt.measure(":")
        except:
            self.pad = 5
        self.create_widgets()
        self.create_menu()

    def on_exit(self):
        self.master.destroy()

    def on_mouse_view(self, event):
        self.update_after()
        
    def on_resize_view(self, event):
        self.update_after()
 
    def parse_path(self, loc):
        if isinstance(loc, str):
            path = []
            if loc[:1] == "/":
                loc = loc[1:]
            if loc != "":
                for item in loc.split("/"):
                    try:
                        path.append(int(item, 10))
                    except:
                        path.append(item)
        else:
            path = loc
        path = tuple(path)
        while path[-1:] == ("",):
            path = path[:-1]
        return path    
 
    def open_path(self, loc, withhist = True):
        path = self.parse_path(loc)        
        if withhist:
            self.hist.append([path])
            self.histf = []
        print("DEBUG: Open", path)
        # set title
        capt = APPNAME
        try:
            if path == ("about",):
                capt = APPNAME + " - " + VERSION
            else:
                capt = APPNAME + " - " + self.desc_path(path)
        except:
            pass
        self.master.title(capt)
        self.curr_path = path
        if len(path) > 0:
            self.curr_help = path[0]
        else:
            self.curr_help = ""
        if len(path) > 0:
            if path[0] in self.path_handler:
                return self.path_handler[path[0]][0](path)
        return self.path_default(path)

    def desc_path(self, loc):
        path = self.parse_path(loc)
        if len(path) > 0:
            if path[0] in self.path_handler:
                desc = self.path_handler[path[0]][1]
                if callable(desc):
                    return desc(path)
                elif desc:
                    return desc
        return self.desc_default(path)

    def update_canvas(self):
        if self.curr_main == 0:          
            return
        # draw grahics
        c = self.canv_view
        c.delete(tkinter.ALL)
        if self.sim is None: return

        w = self.canv_view.winfo_width() 
        h = self.canv_view.winfo_height()
        if (w == 0) or (h == 0): 
            return
        
        scale = 0

        # Preview image
        if not isinstance(self.main_image, tkinter.PhotoImage):
            mw, mh = self.main_image.size
            if scale == 0: # Fit
                try:
                    psc = w / h
                    isc = mw / mh
                    if psc < isc:
                        fact = w / mw
                    else:
                        fact = h / mh
                except:
                    fact = 1.0
            else:
                fact = scale
            pw = int(mw * fact)
            ph = int(mh * fact)
            img = self.main_image.resize((pw, ph), Image.ANTIALIAS)
            self.canv_image = ImageTk.PhotoImage(img)
        else:
            mw = self.main_image.width()
            mh = self.main_image.height()
            if scale == 0: # Fit
                try:
                    psc = w / h
                    isc = mw / mh
                    if psc < isc:
                        if w > mw:
                            fact = w // mw
                        else:
                            fact = -mw // w
                    else:
                        if h > mh:
                            fact = h // mh
                        else:
                            fact = -mh // h
                except:
                    fact = 1
            else:
                fact = scale
            self.canv_image = self.main_image.copy()
            if fact > 0:
                self.canv_image = self.canv_image.zoom(fact)
            else:
                self.canv_image = self.canv_image.subsample(-fact)
            self.canv_image_fact = fact

            # place on canvas
            if fact > 0:
                pw = mw * fact
                ph = mh * fact
            else:
                pw = mw // -fact
                ph = mh // -fact

        cw = max(pw, w)
        ch = max(ph, h)
        c.config(scrollregion = (0, 0, cw - 2, ch - 2))
        #print("Place c %d %d, p %d %d" % (cw, ch, w, h))
        c.create_image(cw // 2, ch // 2, image = self.canv_image)
       
    def make_image(self, imgobj):
        if imgobj.image is not None:
            return imgobj.image
        width = imgobj.width
        height = imgobj.height
        data = imgobj.rgb
        # create P6
        phdr = ("P6\n{} {}\n255\n".format(width, height))
        rawlen = width * height * 3 # RGB
        #phdr = ("P5\n{} {}\n255\n".format(width, height))
        #rawlen = width * height
        phdr = phdr.encode("UTF-8")

        if len(data) > rawlen:
            # truncate
            pdata = data[:rawlen]
        if len(data) < rawlen:
            # fill gap
            gap = bytearray()
            data += b"\xff" * (rawlen - len(data))
        p = bytearray(phdr)
        # fix UTF-8 issue
        for ch in data:
            if ch > 0x7f:
                p += bytes((0b11000000 |\
                    ch >> 6, 0b10000000 |\
                    (ch & 0b00111111)))               
            else:
                p += bytes((ch,))
        image = tkinter.PhotoImage(width = width, height = height, \
            data = bytes(p))
        return image                
   
    def update_gui(self, text = "<Undefined>"):
        self.last_path = self.curr_path
        # cleanup
        for item in self.curr_gui:
            item()
        self.curr_gui = []
        self.curr_state = {} # save state across moves
        # left listbox
        lab = tkinter.Label(self.frm_left, text = text)
        lab.pack()
        frm_lb = ttk.Frame(self.frm_left)
        frm_lb.pack(fill = tkinter.BOTH, expand = 1)
        frm_lb.grid_rowconfigure(0, weight = 1)
        frm_lb.grid_columnconfigure(0, weight = 1)
        scr_lb_x = ttk.Scrollbar(frm_lb, orient = tkinter.HORIZONTAL)
        scr_lb_x.grid(row = 1, column = 0, sticky = tkinter.E + tkinter.W)
        scr_lb_y = ttk.Scrollbar(frm_lb)
        scr_lb_y.grid(row = 0, column = 1, sticky = tkinter.N + tkinter.S)
        frmlbpad = ttk.Frame(frm_lb, borderwidth = self.pad)
        lb = tkinter.Listbox(frm_lb,
            highlightthickness = 0,
            xscrollcommand = scr_lb_x.set,
            yscrollcommand = scr_lb_y.set)
        lb.grid(row = 0, column = 0, \
            sticky = tkinter.N + tkinter.S + tkinter.E + tkinter.W)
        scr_lb_x.config(command = lb.xview)
        scr_lb_y.config(command = lb.yview)
        self.curr_gui.append(lambda:lb.grid_remove())
        self.curr_gui.append(lambda:lab.pack_forget())
        self.curr_gui.append(lambda:frm_lb.pack_forget())
        lb.bind("<Double-Button-1>", self.on_left_listbox)
        lb.bind("<Return>", self.on_left_listbox)
        # actions on listbox
        self.curr_lb = lb
        self.curr_lb_acts = []
        self.curr_lb_idx = {}

    def switch_view(self, main):
        # main view
        if main == self.curr_main: return
        last = self.curr_main
        self.curr_main = main
        rw = None
        rh = None
        if main == 0:
            self.canv_view.delete(tkinter.ALL)
            self.canv_view.grid_forget()
            self.text_view.grid(row = 0, column = 0, \
                sticky = tkinter.N + tkinter.S + tkinter.E + tkinter.W)
            self.text_view.configure(
                xscrollcommand = self.scr_view_x.set,
                yscrollcommand = self.scr_view_y.set
            )
            self.scr_view_x.config(command = self.text_view.xview)
            self.scr_view_y.config(command = self.text_view.yview)
        else:
        
            if last == 0:
                rw = self.text_view.winfo_width()
                rh = self.text_view.winfo_height()
            self.canv_view.delete(tkinter.ALL)
            self.text_view.grid_forget()
            self.canv_view.grid(row = 0, column = 0, \
                sticky = tkinter.N + tkinter.S + tkinter.E + tkinter.W)
            self.canv_view.configure(
                xscrollcommand = self.scr_view_x.set,
                yscrollcommand = self.scr_view_y.set
            )
            self.scr_view_x.config(command = self.canv_view.xview)
            self.scr_view_y.config(command = self.canv_view.yview)
            if rh:
                print(rh)
                self.canv_view.height = rh
                print(self.canv_view.winfo_height())

    def clear_info(self):
        self.text_view.delete(0.0, tkinter.END)

    def add_info(self, text):
        mode = 0 # 0 - normal, 1 - tag
        curr_tag = None
        curr_text = ""
        tags = []
        esc = False
        for ch in text:
            if mode == 0:
                if esc:
                    curr_text += ch
                    esc = False
                else:
                    if ch == "\\":
                        esc = True
                    elif ch == "<":
                        mode = 1
                        curr_tag = ""
                    else:
                        curr_text += ch
            else:
                if ch == ">":
                    if len(curr_text) > 0:                    
                        self.text_view.insert(tkinter.INSERT, curr_text, \
                            tuple(reversed([x for x in tags for x in x])))
                    if curr_tag[:7] == "a href=":
                        ref = curr_tag[7:]
                        if ref[:1] == "\"":
                            ref = ref[1:]
                        if ref[-1:] == "\"":
                            ref = ref[:-1]
                        def make_cb(path):
                            def cb():
                                return self.open_path(path)
                            return cb
                        tags.append(self.text_hl.add(make_cb(ref)))
                    elif curr_tag[:11] == "font color=":
                        ref = curr_tag[11:]
                        if ref[:1] == "\"":
                            ref = ref[1:]
                        if ref[-1:] == "\"":
                            ref = ref[:-1]
                        tags.append(self.text_hl.color(ref))
                    elif curr_tag[:8] == "font bg=":
                        ref = curr_tag[8:]
                        if ref[:1] == "\"":
                            ref = ref[1:]
                        if ref[-1:] == "\"":
                            ref = ref[:-1]
                        tags.append(self.text_hl.bg(ref))
                    elif curr_tag == "b":
                        tags.append(["bold"])
                    elif curr_tag == "i":
                        tags.append(["italic"])
                    elif curr_tag == "u":
                        tags.append(["underline"])
                    elif curr_tag[:1] == "/":
                        tags = tags[:-1]
                    curr_text = ""
                    mode = 0
                else:
                    curr_tag += ch
        if len(curr_text) > 0: 
            self.text_view.insert(tkinter.INSERT, curr_text, \
                tuple(reversed([x for x in tags for x in x])))
        
    def insert_lb_act(self, name, act, key = None):
        if key is not None:
            self.curr_lb_idx[key] = len(self.curr_lb_acts)
        self.curr_lb_acts.append((name, act))
        if name == "-" and act is None:
            self.curr_lb.insert(tkinter.END, "")
        else:
            self.curr_lb.insert(tkinter.END, " " + name)

    def select_lb_item(self, key):
        idx = self.curr_lb_idx.get(key, None)
        need = (idx is not None)
        idxs = "{}".format(idx)
        for sel in self.curr_lb.curselection():
            if sel == idxs:
                need = False
            else:
                self.curr_lb.selection_clear(sel)
        if need:
            self.curr_lb.selection_set(idxs)
        if idx is not None:
            self.curr_lb.see(idxs)
            
    def on_left_listbox(self, event):
        def currsel():
            try:
                num = self.curr_lb.curselection()[0]
                num = int(num)
            except:
                return None
            return num

        if self.curr_lb_acts:
            act = self.curr_lb_acts[currsel()]
            if act[1] is not None:
                self.open_path(act[1])

    def add_toolbtn(self, text, cmd):
        if text is None:
            frm = ttk.Frame(self.toolbar, width = self.pad, height = self.pad)
            frm.pack(side = tkinter.LEFT)
            self.curr_gui.append(lambda:frm.pack_forget())    
            return
        btn = ttk.Button(self.toolbar, text = text, \
            style = "Tool.TButton", command = cmd)
        btn.pack(side = tkinter.LEFT)
        self.curr_gui.append(lambda:btn.pack_forget())
        return btn
        
    def add_toollabel(self, text):
        lab = ttk.Label(self.toolbar, text = text)
        lab.pack(side = tkinter.LEFT)
        self.curr_gui.append(lambda:lab.pack_forget())
        return lab

    def add_toolgrp(self, label, glkey, items, cbupd):
        def makecb(v, g):
            def btncb():
                self.gl_state[g] = v
                cbupd()
            return btncb
        if label:
            self.add_toollabel(label)
        kl = list(items.keys())
        kl.sort()
        res = []
        for k in kl:
            b = self.add_toolbtn(items[k], makecb(k, glkey))
            res.append([b, k])
        return res

    def upd_toolgrp(self, btns, state):
        for btn, idx in btns:
            if idx != state and state != -1:
                btn.config(state = tkinter.NORMAL)
            else:
                btn.config(state = tkinter.DISABLED)
    

    def clear_hist(self):
        self.hist = self.hist[-1:]
        self.histf = []

    def on_help(self):
        self.open_path(["help", self.curr_help])

    def on_back(self):
        if len(self.hist) > 1:
            np = self.hist[-2:-1][0]
            self.histf = self.hist[-1:] + self.histf
            self.hist = self.hist[:-1]
            self.open_path(np[0], False)

    def on_forward(self):
        if len(self.histf) > 0:
            np = self.histf[0]
            self.histf = self.histf[1:]
            self.hist.append(np)
            self.open_path(np[0], False)

    def _t(self, value, tp):
        if not self.tran: return value
        if tp in self.tran:
            if value in self.tran[tp]:
                return self.tran[tp][value]
        if value in self.tran["_"]:
            return self.tran["_"][value]
        return value

    def fmt_opcode(self, opcode, nofmt = False):
        if nofmt:
            return petka.OPCODES.get(opcode, ["OP{:04X}".format(opcode)])[0]
        return petka.OPCODES.get(opcode, ["<font color=\"red\">OP{:04X}</font>".\
            format(opcode)])[0]

    def fmt_dlgop(self, opcode, nofmt = False):
        if nofmt:
            return petka.DLGOPS.get(opcode, ["OP{:02X}".\
                format(opcode)])[0]
        return petka.DLGOPS.get(opcode, ["<font color=\"red\">OP{:02X}</font>".\
            format(opcode)])[0]

    def fmt_cmt(self, cmt):
        return "<font color=\"#4d4d4d\">{}</font>".format(cmt)

    def fmt_hl_rec(self, lst_idx, pref, rec_id, full, tt):
        if rec_id in lst_idx:
            fmt = fmt_hl("/{}/{}".format(pref, rec_id), str(rec_id))
            if full:
                try:
                    fmt += " (0x{:X}) - {}".format(rec_id, 
                        hlesc(self._t(lst_idx[rec_id].name, tt)))
                except:
                    fmt += " (0x{:X})".format(rec_id)
            return fmt
        return "{} (0x{:X})".format(rec_id, rec_id)
        
    def fmt_hl_obj(self, obj_id, full = False):
        return self.fmt_hl_rec(self.sim.obj_idx, "objs", obj_id, full, "obj")
        
    def fmt_hl_scene(self, scn_id, full = False):
        return self.fmt_hl_rec(self.sim.scn_idx, "scenes", scn_id, full, "scn")

    def fmt_hl_obj_scene(self, rec_id, full = False):
        if rec_id in self.sim.obj_idx:
            return self.fmt_hl_rec(self.sim.obj_idx, "objs", rec_id,
                full, "obj")
        return self.fmt_hl_rec(self.sim.scn_idx, "scenes", rec_id, full, "scn")
        
    def find_path_name(self, key):
        for name_id, name in enumerate(self.sim.namesord):
            if name == key:
                return "/names/{}".format(name_id)
        return "/no_name/{}".format(key)

    def find_path_invntr(self, key):
        for inv_id, name in enumerate(self.sim.invntrord):
            if name == key:
                return "/invntr/{}".format(inv_id)
        return "/no_invntr/{}".format(key)

    def find_path_cast(self, key):
        for cast_id, name in enumerate(self.sim.castsord):
            if name == key:
                return "/casts/{}".format(cast_id)
        return "/no_casts/{}".format(key)

    def fmt_hl_msg(self, msg_id, full = False):
        msg_idx = {}
        if msg_id < len(self.sim.msgs):
            msg_idx[msg_id] = self.sim.msgs[msg_id]
        return self.fmt_hl_rec(msg_idx, "msgs", msg_id, full, "msg")

    def fmt_hl_dlg(self, grp_id, full = False):
        return self.fmt_hl_rec(self.sim.dlg_idx, "dlgs", grp_id, full, "dlg")

    def path_info_outline(self):
        if self.sim is None and self.strfm is None:
            self.add_info("No data loaded. Open PARTS.INI or SCRIPT.DAT first.")
            return
        if self.sim:
            self.add_info("Current part {} chapter {}\n\n".\
                    format(self.sim.curr_part, self.sim.curr_chap))
            self.add_info("  Resources:     " + fmt_hl("/res", 
                len(self.sim.res)) + "\n")
            self.add_info("  Objects:       " + fmt_hl("/objs", 
                len(self.sim.objects)) + "\n")
            self.add_info("  Scenes:        " + fmt_hl("/scenes", 
                len(self.sim.scenes)) + "\n")
            self.add_info("  Names:         " + fmt_hl("/names", 
                len(self.sim.names)) + "\n")
            self.add_info("  Invntr:        " + fmt_hl("/invntr", 
                len(self.sim.invntr)) + "\n")
            self.add_info("  Casts:         " + fmt_hl("/casts", 
                len(self.sim.casts)) + "\n")
            self.add_info("  Messages       " + fmt_hl("/msgs", 
                len(self.sim.msgs)) + "\n")
            self.add_info("  Dialog groups: " + fmt_hl("/dlgs", 
                len(self.sim.dlgs)) + "\n")
            self.add_info("  Opened stores: " + fmt_hl("strs", 
                len(self.strfm.strfd)) + "\n")
            self.add_info("  Files:         " + fmt_hl("/files", 
                len(self.strfm.strtable)) + "\n")
            scn = hlesc(self.sim.start_scene)
            for scene in self.sim.scenes:
                if scene.name == self.sim.start_scene:
                    scn = self.fmt_hl_scene(scene.idx, True)
                    break
            self.add_info("  Start scene:   {}\n".format(scn))
            self.add_info("\n")
            self.add_info("  " + fmt_hl("/opcodes", "Opcodes") + "\n")
            self.add_info("  " + fmt_hl("/dlgops", "Dialog opcodes") + "\n")
        elif self.strfm:
            self.add_info("Single store mode\n\n")
            self.add_info("  Opened stores: " + fmt_hl("/strs", 
                len(self.strfm.strfd)) + "\n")
            self.add_info("  Files:         " + fmt_hl("/files", 
                len(self.strfm.strtable)) + "\n")
        if self.save:
            self.add_info("  " + fmt_hl("/save", "Save") + "\n")

    def show_hist(self):
        self.switch_view(0)
        self.clear_info()
        self.add_info("<b>History</b>\n\n")
        sz = max(len(self.hist[:-1]), len(self.histf))
        fmt = fmt_dec(sz, 1)
        fmt = "  " + fmt + ") {}\n"
        for idx, h in enumerate(self.hist[:-1]):
            self.add_info(fmt.format(idx - len(self.hist) + 1, 
                self.desc_path(h[0])))
        self.add_info(" {} {}\n".format("=" * fmt_dec_len(sz, 2) + ">", 
            self.desc_path(self.curr_path)))
        for idx, h in enumerate(self.histf):
            self.add_info(fmt.format(idx + 1, self.desc_path(h[0])))
            
    def desc_default(self, path):
        desc = ""
        for item in path:
            desc += "/{}".format(item)
        if not desc:
            desc = "Outline"
        return desc
        
    def path_default(self, path):
        self.switch_view(0)
        self.update_gui("Outline")
        self.clear_info()
        if len(path) != 0:
            spath = ""
            for item in path:
                spath += "/" + str(item)
            self.add_info("Path {} not found\n\n".format(spath))
        if self.sim or self.strfm:
            self.add_info("Select from <b>outline</b>\n\n")
        self.path_info_outline()
        if self.sim is not None:
            acts = [
                ("Parts ({})".format(len(self.sim.parts)), "/parts"),
                ("Resources ({})".format(len(self.sim.res)), "/res"),
                ("Objects ({})".format(len(self.sim.objects)), "/objs"),
                ("Scenes ({})".format(len(self.sim.scenes)), "/scenes"),
                ("Names ({})".format(len(self.sim.names)), "/names"),
                ("Invntr ({})".format(len(self.sim.invntr)), "/invntr"),
                ("Casts ({})".format(len(self.sim.casts)), "/casts"),
                ("Messages ({})".format(len(self.sim.msgs)), "/msgs"),
                ("Dialog groups ({})".format(len(self.sim.dlgs)), "/dlgs"),
                ("Opcodes", "/opcodes"),
                ("Dialog opcodes", "/dlgops"),
                #("-", None),
                #("Test image", ["test", "image"]),
                #("Test info", ["test","info"]),
            ]
            for name, act in acts:
                self.insert_lb_act(name, act)
        if self.strfm is not None:
            acts = [
                ("Stores ({})".format(len(self.strfm.strfd)), "/strs"),
                ("Files ({})".format(len(self.strfm.strtable)), "/files"),
            ]
            for name, act in acts:
                self.insert_lb_act(name, act)

        if self.save is not None:
            acts = [
                ("Save", "/save"),
            ]
            for name, act in acts:
                self.insert_lb_act(name, act)
        return True

    def desc_parts(self, path):
        # this part can be internationalized
        if len(path) > 1:
            try:
                part = path[1]
                part = part.split(".", 1)
                part[0] = int(part[0])
                part[1] = int(part[1])
            except:
                part = None
                pass
                return "Goto to unknown part {}".format(path[1])
            return "Select part {} chapter {}".format(part[0], part[1])
        return "Select part"

    def path_parts(self, path):
        if self.sim is None:
            return self.path_default([])

        self.switch_view(0)
        if self.last_path[:1] != ("parts",):
            self.update_gui("Parts ({})".format(len(self.sim.parts)))
            for name in self.sim.parts:
                pnum = name[5:]
                cnum = pnum.split("Chapter", 1)
                if len(cnum) > 1:
                    pnum = int(cnum[0].strip(), 10)
                    cnum = int(cnum[1].strip(), 10)
                else:
                    cnum = 0
                part_id = "{}.{}".format(pnum, cnum)
                self.insert_lb_act(name, ["parts", part_id], part_id)
            if len(self.sim.parts) == 0:
                # Option to fix paths
                def fix_paths():
                    self.sim.curr_path = ""
                    path = self.sim.fman.root
                    while self.sim.curr_path == "":
                       self.sim.curr_path = os.path.basename(path)
                       path2 = os.path.dirname(path)
                       if path2 == path: break
                       path = path2
                    path = self.sim.fman.root = path
                    self.sim.curr_path += "\\"
                self.add_toolbtn("Fix paths", fix_paths)

        # change
        part = None
        if len(path) > 1:
            # parts
            self.select_lb_item(path[1])
            try:
                part = path[1]
                part = part.split(".", 1)
                part[0] = int(part[0])
                part[1] = int(part[1])
            except:
                part = None
                pass
        else:
            self.select_lb_item(None)
        # display
        self.clear_info()
        if not part:
            self.add_info("Select <b>part</b>\n\n")
            self.path_info_outline()
        else:
            try:
                self.clear_hist()
                self.sim.open_part(part[0], part[1])
                self.path_info_outline()
            except:
                self.add_info("Error open part {} chapter {} - \n\n{}".\
                    format(part[0], part[1], hlesc(traceback.format_exc())))
                return False
        return True
        
    def desc_res(self, path):
        if path == ("res",):
            path = ("res", "all")
        if path[1] == "flt":
            if len(path) > 2:
                return "Resource type {}".format(path[2])
            return "Resources by type"
        if path[1] == "all":
            if len(path) > 2:
                return "Resource {}".format(path[2])
            return "Resources"
        return self.path_default(path)

    def path_res(self, path):
        # res - full list
        # res/flt/<ext> - list by <ext>
        # res/all/<id> - display res by id
        if self.sim is None:
            return self.path_default([])
        if path == ("res",):
            path = ("res", "all")
        if path[1] == "flt":
            return self.path_res_flt(path)
        elif path[1] == "all":
            return self.path_res_all(path)
        else:
            return self.path_default(path)

    def path_res_open(self, pref, res_id, mode):
        self.curr_help = "res_view" # help override 
        if res_id not in self.sim.res:        
            self.switch_view(0)
            self.clear_info()
            self.add_info("<b>Resource</b> \"{}\" not found\n".format(res_id))
            return
        self.select_lb_item(res_id)
        resref = "/" + "/".join([str(x) for x in pref])
        if len(mode) == 0:
            self.switch_view(0)
            fn = self.sim.res[res_id]
            self.clear_info()
            self.add_info("<b>Resource</b>: {} (0x{:X}) - \"{}\"\n\n".\
                format(res_id, res_id, hlesc(fn)))
            self.add_info("<a href=\"{}/view\">View</a>\n\n".\
                format(resref, resref))
            try:
                if fn[-4:].lower() == ".bmp":
                    self.add_info("<b>BMP image</b>: ")
                    bmpf = self.sim.fman.read_file_stream(fn)
                    bmp = petka.BMPLoader()
                    bmp.load_info(bmpf)
                    if bmp.image:
                        # PIL
                        self.add_info("Python Imaging\n")
                        self.add_info("  Mode: {}\n  Size: {}x{}".\
                            format(bmp.image.mode, \
                                bmp.image.size[0], bmp.image.size[1]))
                    else:    
                        self.add_info("internal BMP loader\n"\
                            "  Mode: 16-bit\n  Size: {}x{}".\
                            format(bmp.width, bmp.height))
                elif fn[-4:].lower() == ".flc":
                    self.add_info("<b>FLC animation</b>: ")
                    flcf = self.sim.fman.read_file_stream(fn)
                    flc = petka.FLCLoader()
                    flc.load_info(flcf)
                    if flc.image:
                        # PIL
                        self.add_info("Python Imaging\n")
                        self.add_info("  Mode:   {}\n  Size:   {}x{}\n"
                            "  Frames: {}\n  Delay:  {}".\
                            format(flc.image.mode, \
                                flc.image.size[0], flc.image.size[1],
                                flc.frame_num, flc.image.info["duration"]))
                    else:    
                        self.add_info("internal FLC loader\n  "\
                            "  Mode:   P\n  Size:   {}x{}\n"\
                            "  Frames: {}\nDelay: {}".\
                            format(flc.width, flc.height, \
                                flc.frame_num, flc.delay))
                else:
                    self.add_info("No information availiable")
            except:
                self.add_info("Error loading {} - \"{}\" \n\n{}".\
                    format(res_id, hlesc(fn), hlesc(traceback.format_exc())))

            def usedby(lst):
                for idx, rec in enumerate(lst):
                    ru = False
                    for act in rec.acts:
                        if ru: break
                        for op in act.ops:
                            if res_id == op.op_arg1:
                                self.add_info("  " + 
                                    self.fmt_hl_obj_scene(rec.idx, True) + "\n")
                                ru = True
                                break

            self.add_info("\n\n<b>Used by objects</b>:\n")
            usedby(self.sim.objects)
            self.add_info("\n<b>Used by scenes</b>:\n")
            usedby(self.sim.scenes)
            self.add_info("\nFile: {}\n".format(self.fmt_hl_file(fn)))
            
                    
        elif mode[0] == "view":
            self.path_res_view(res_id)
        return True
                
    def path_res_view(self, res_id):
        fn = self.sim.res[res_id]
        try:
            dataf = self.sim.fman.read_file_stream(fn)
            if fn[-4:].lower() == ".bmp":
                bmp = petka.BMPLoader()
                bmp.load_data(dataf)
                self.main_image = \
                    self.make_image(bmp)
                self.switch_view(1)
                self.update_canvas()
            elif fn[-4:].lower() == ".flc":
                flcf = self.sim.fman.read_file_stream(fn)
                flc = petka.FLCLoader()
                flc.load_data(dataf)
                self.main_image = \
                    self.make_image(flc)
                self.switch_view(1)
                self.update_canvas()
            else:
                self.switch_view(0)
                self.clear_info()
                self.add_info("Resource {} - \"{}\" cannot be displayed\n".\
                    format(res_id, hlesc(fn)))
        except:
            self.switch_view(0)
            self.clear_info()
            self.add_info("Error loading {} - \"{}\" \n\n{}".\
                format(res_id, hlesc(fn), hlesc(traceback.format_exc())))
            dataf = None
        finally:
            if dataf:
                dataf.close()
        return True

    def path_res_status(self):
        self.switch_view(0)
        self.clear_info()
        self.add_info("<b>Resources</b>: " + fmt_hl("/res", len(self.sim.res)) 
            + "\nFiletypes:\n")
        fts = {}
        for res in self.sim.res.values():
            fp = res.rfind(".")
            if fp >= 0:
                ft = res[fp + 1:].upper()
                fts[ft] = fts.get(ft, 0) + 1
        ftk = list(fts.keys())
        ftk.sort()
        for ft in ftk:
            self.add_info("  <a href=\"/res/flt/{}\">{}</a>: {}\n".format(
                ft, ft, fts[ft]))
        self.select_lb_item(None)
        return True
    
    def on_path_res_info(self):
        self.switch_view(0)
        
    def on_path_res_view(self):
        self.switch_view(1)

    def path_res_all(self, path):
        if self.last_path[:2] != ("res", "all",) and self.last_path != ("res",):
            self.update_gui("Resources ({})".format(len(self.sim.res)))
            #self.add_toolbtn("Info", self.on_path_res_info)
            #self.add_toolbtn("View", self.on_path_res_view)
            for res_id in self.sim.resord:
                    self.insert_lb_act("{} - {}".format(\
                res_id, self.sim.res[res_id]), ["res", "all", res_id], res_id)
        # change                
        if len(path) > 2:
            return self.path_res_open(path[:3], path[2], path[3:])
        else:
            return self.path_res_status()

    def path_res_flt(self, path):
        lst = []
        for idx, res_id in enumerate(self.sim.resord):
            if self.sim.res[res_id].upper().endswith("." + path[2]):
                lst.append(res_id)
        if self.last_path[:3] != ("res", "flt", path[2]):
            self.update_gui("Resources {} ({})".format(path[2], len(lst)))
            self.insert_lb_act("All", "/res")
            self.insert_lb_act("-", None)
            for res_id in lst:
                    self.insert_lb_act("{} - {}".format(\
                res_id, self.sim.res[res_id]), ["res", "flt", path[2], res_id], 
                    res_id)
        # change                
        if len(path) > 3:
            return self.path_res_open(path[:4], path[3], path[4:])
        else:
            return self.path_res_status()

    def path_objs_scenes(self, path):
        if self.sim is None:
            return self.path_default([])
        self.switch_view(0)
        isobj = (self.curr_path[0] == "objs")
        if isobj:
            lst = self.sim.objects
            lst_idx = self.sim.obj_idx
        else:
            lst = self.sim.scenes
            lst_idx = self.sim.scn_idx
        if self.last_path[:1] != (self.curr_path[0],):
            if isobj:
                self.update_gui("Objects ({})".format(len(lst)))
            else:
                self.update_gui("Scenes ({})".format(len(lst)))
            for rec in lst:
                self.insert_lb_act("{} - {}".format(rec.idx, 
                    self._t(rec.name, "obj" if isobj else "scn")),\
                    [self.curr_path[0], rec.idx], rec.idx)
        # change                
        rec = None
        if len(path) > 1:
            # index
            self.select_lb_item(path[1])
            try:
                rec = lst_idx[path[1]]
            except:
                pass
        else:
            self.select_lb_item(None)
        # display
        self.clear_info()
        if not rec:
            if len(path) > 1:
                self.add_info("Item \"{}\" at <b>{}</b> not found\n\n".format(
                    path[1], path[0]))
            self.add_info("Select item from list\n")
        else:
            # record info
            self.add_info(("<b>Object</b>" if isobj \
                else "<b>Scene</b>") + ":\n")
            self.add_info("  Index:     {} (0x{:X})\n".format(rec.idx, rec.idx))
            self.add_info("  Name:      {}\n".format(hlesc(rec.name)))
            if self.tran:
                self.add_info("  Name(t):   {}\n".\
                    format(hlesc(self._t(rec.name, "obj" if isobj else "scn"))))
                if rec.name in self.sim.names:
                    self.add_info("  " + fmt_hl(self.find_path_name(rec.name), 
                        "Alias") + "(t):  {}\n".format(
                            hlesc(self._t(self.sim.names[rec.name], "obj"))))
                if rec.name in self.sim.invntr:
                    self.add_info("  " + fmt_hl(self.find_path_invntr(rec.name), 
                        "Invntr") + "(t): {}\n".format(
                            hlesc(self._t(self.sim.invntr[rec.name], "inv"))))
            else:
                if rec.name in self.sim.names:
                    self.add_info("  " + fmt_hl(self.find_path_name(rec.name), 
                        "Alias") + ":     {}\n".format(
                            hlesc(self.sim.names[rec.name])))
                if rec.name in self.sim.invntr:
                    self.add_info("  " + fmt_hl(self.find_path_invntr(rec.name), 
                        "Invntr") + ":    {}\n".format(
                            hlesc(self.sim.invntr[rec.name])))
            if rec.cast:
                bg = 0
                r = rec.cast[0] 
                g = rec.cast[1]
                b = rec.cast[2]
                if (r + g * 2 + b) // 3 < 160: 
                    bg = 255
                self.add_info("  " + fmt_hl(self.find_path_cast(rec.name), 
                    "Cast") + ":      <font bg=\"#{bg:02x}{bg:02x}{bg:02x}\">"
                    "<font color=\"#{r:02x}{g:02x}{b:02x}\">"\
                    "<b> #{r:02x}{g:02x}{b:02x} </b></font></font>\n".\
                    format(bg = bg, r = r, g = g, b = b))
            
            # references / backreferences                    
            if isobj:
                # search where object used
                self.add_info("\n<b>Refered by scenes</b>:\n")
                for scn in self.sim.scenes:
                    for ref in scn.refs:
                        if ref[0].idx == rec.idx:
                            self.add_info("  " + 
                                self.fmt_hl_scene(scn.idx, True) + "\n")
                            break
            else:
                if len(rec.refs) == 0:
                    self.add_info("\nNo references\n")
                else:
                    self.add_info("\n<b>References</b>: {}\n".\
                        format(len(rec.refs)))
                fmtd = "  " + fmt_dec(len(rec.refs)) + ") "
                for idx, ref in enumerate(rec.refs):
                    self.add_info(fmtd.format(idx) + 
                        self.fmt_hl_obj(ref[0].idx))
                    msg = ""
                    for arg in ref[1:]:
                        msg += " "
                        if arg < 10:
                            msg += "{}".format(arg)
                        elif arg == 0xffffffff:
                            msg += "-1"
                        else:
                            msg += "0x{:X}".format(arg)
                    self.add_info(msg + self.fmt_cmt(" // " + self.fmt_hl_obj(
                        ref[0].idx, True)) + "\n")

            resused = []
            dlgused = []
            self.add_info("\n<b>Handlers</b>: {}\n".format(len(rec.acts)))
            fmtra = "  " + fmt_dec(len(rec.acts)) + \
                ") <u>on {}</u>, ops: {}{}\n"
            for idx, act in enumerate(rec.acts):
                msg = self.fmt_opcode(act.act_op)
                cmt = ""
                if act.act_status != 0xff or act.act_ref != 0xffff:
                    act_ref = act.act_ref
                    if act.act_ref == rec.idx:
                        act_ref = "THIS"
                    else:
                        if act.act_ref in self.sim.obj_idx:
                            cmt = self.fmt_cmt(" // " + self.fmt_hl_obj(
                                act.act_ref, True))
                            act_ref = self.fmt_hl_obj(act.act_ref)
                        else:
                            act_ref = "0x{:X}".format(act.act_ref)
                    msg += " 0x{:02X} {}".format(act.act_status, act_ref)
                self.add_info(fmtra.format(idx, msg, len(act.ops), cmt))
                fmtao = "    " + fmt_dec(len(act.ops)) + ")"
                for oidx, op in enumerate(act.ops):
                    self.add_info(self.fmt_cmt(fmtao.format(oidx)))
                    self.add_info(" " + self.fmt_opcode(op.op_code) + " ")
                    cmt = ""
                    if op.op_ref == rec.idx:
                        self.add_info("THIS")
                    else:
                        self.add_info(self.fmt_hl_obj_scene(op.op_ref))
                        cmt = self.fmt_cmt(" // " + self.fmt_hl_obj_scene(
                            op.op_ref, True))
                    msg = ""
                    if op.op_arg1 != 0xffff:
                        if op.op_arg1 not in resused and \
                                op.op_arg1 in self.sim.res:
                            resused.append(op.op_arg1)
                    msg += " " + fmt_arg(op.op_arg1)
                    msg += " " + fmt_arg(op.op_arg2)
                    msg += " " + fmt_arg(op.op_arg3)
                    self.add_info("{}{}\n".format(msg, cmt))
                    if op.op_code == 0x11: # DIALOG
                        if op.op_ref not in dlgused:
                            dlgused.append(op.op_ref)
                    
            if len(resused) > 0:
                self.add_info("\n<b>Used resources</b>: {}\n".\
                    format(len(resused)))
                for res_id in resused:
                    self.add_info("  " + fmt_hl("/res/all/{}".format(res_id), 
                        "{}".format(res_id)) + " (0x{:X}) - {}\n".format(res_id,
                            hlesc(self.sim.res[res_id])))
            if len(dlgused) > 0:
                self.add_info("\n<b>Used dialog groups</b>: {}\n".\
                    format(len(dlgused)))
                for grp_id in dlgused:
                    self.add_info("  " + self.fmt_hl_dlg(grp_id, True)+ "\n")

            # messages used by this object            
            if isobj:
                wasmsg = False
                for msg in self.sim.msgs:
                    if msg.obj.idx != rec.idx: continue
                    if not wasmsg:
                        self.add_info("\n<b>Messages</b>:\n")
                        wasmsg = True
                    self.add_info("  " + self.fmt_hl_msg(msg.idx, True) + "\n")

            oplst = {}
            # objects tan use this objects in TALK opcode
            wasmsg = False
            for obj2 in self.sim.objects + self.sim.scenes:
                if obj2.idx == rec.idx: continue
                for idx, act in \
                        enumerate(obj2.acts):
                    for oidx, op in enumerate(act.ops):
                        if op.op_ref == rec.idx:
                            arr = oplst.get(op.op_code, [])
                            arr.append((obj2.idx, act.act_op, idx))
                            oplst[op.op_code] = arr
                            break

            klst = list(petka.OPCODES.keys())
            klst.sort()
            for k in klst:
                if k not in oplst: continue
                self.add_info("\n<b>Used in " + self.fmt_opcode(k) + "</b>:\n")
                for oid, htp, hid in oplst[k]:
                    self.add_info("  " + self.fmt_hl_obj_scene(oid) + 
                      " on " + self.fmt_opcode(htp) + 
                      " #{}".format(hid) + self.fmt_cmt(" // " + 
                      self.fmt_hl_obj_scene(oid, True)) + "\n")

            # perspective
            if not isobj and rec.persp:
                self.add_info("\n<b>Perspective</b>:\n  {}, {}, {}, {}, {}\n".
                    format(*rec.persp))
                
            # enter areas
            if not isobj and rec.entareas:
                self.add_info("\n<b>Enter areas</b>: {}\n".format(
                    len(rec.entareas)))
                for sf, oo in rec.entareas:
                    self.add_info("  <i>from</i>: {}\n".format(
                        self.fmt_hl_scene(sf.idx, True)))
                    self.add_info("    <i>on</i>: {}\n".format(
                        self.fmt_hl_obj(oo.idx, True)))
        return True
                
    def path_std_items(self, path, level, guiname, guiitem, tt, lst, lst_idx, 
            lbmode, cb):
        self.switch_view(0)
        if self.last_path[:level] != path[:level]:
            self.update_gui("{} ({})".format(guiname, len(lst)))
            for idx, name in enumerate(lst_idx):
                lb = self._t(name, tt)
                if lbmode == 1:
                    lb = "{} - {}".format(name, self._t(lst[name], tt))
                self.insert_lb_act(lb, path[:level] + tuple([idx]), idx)
        # change
        name = None
        if len(path) > 1:
            # lb
            self.select_lb_item(path[1])
            try:
                name = lst_idx[path[1]]
            except:
                pass
        else:
            self.select_lb_item(None)
        # display
        self.clear_info()
        if not name:
            self.add_info("Select <b>{}</b> from list\n".format(guiitem))
        else:
            # info
            cb(name)
        return True
        
    def path_names(self, path):
        if self.sim is None:
            return self.path_default([])
        def info(name):
            self.add_info("<b>Alias</b>:    {}\n".format(hlesc(name)))
            if self.tran:
                self.add_info("<b>Alias</b>(t): {}\n".\
                    format(hlesc(self._t(name, "obj"))))
            self.add_info("Value:    {}\n".format(self.sim.names[name]))
            if self.tran:
                self.add_info("Value(t): {}\n".\
                    format(hlesc(self._t(self.sim.names[name], "name"))))
            # search for objects
            self.add_info("\n<b>Applied for</b>:\n")
            for obj in self.sim.objects:
                if obj.name == name:
                    self.add_info("  " + self.fmt_hl_obj(obj.idx, True) + "\n")
        return self.path_std_items(path, 1, "Names", "name", "obj", 
            self.sim.names, self.sim.namesord, 0, info)
                            
    def path_invntr(self, path):
        if self.sim is None:
            return self.path_default([])
        def info(name):
            self.add_info("<b>Invntr</b>:    {}\n".format(hlesc(name)))
            if self.tran:
                self.add_info("<b>Invntr</b>(t): {}\n".\
                    format(hlesc(self._t(name, "obj"))))
            self.add_info("{}\n\n".format(hlesc(self.sim.invntr[name])))
            if self.tran:
                self.add_info("<i>Translated</i>\n{}\n\n".\
                    format(hlesc(self._t(self.sim.invntr[name], "inv"))))
            # search for objects
            self.add_info("<b>Applied for</b>:\n")
            for obj in self.sim.objects:
                if obj.name == name:
                    self.add_info("  " + self.fmt_hl_obj(obj.idx, True) + "\n")
        return self.path_std_items(path, 1, "Invntr", "invntr", "obj", 
            self.sim.invntr, self.sim.invntrord, 0, info)

    def path_casts(self, path):
        if self.sim is None:
            return self.path_default([])
        def info(name):
            self.add_info("<b>Cast</b>:    {}\n".format(hlesc(name)))
            if self.tran:
                self.add_info("<b>Cast</b>(t): {}\n".\
                    format(hlesc(self._t(name, "obj"))))
            self.add_info("Value:    {}\n".format(self.sim.casts[name]))
            try:
                val = self.sim.casts[name].split(" ")
                val = [x for x in val if x]
                r = int(val[0])
                g = int(val[1])
                b = int(val[2])
            except:
                r, g, b = 0, 0, 0
            hl = "<font bg=\"#{:02x}{:02x}{:02x}\">        </font>".\
                format(r, g, b)
            self.add_info("  " + hl + "\n")
            self.add_info("  " + hl + "\n\n")
            # search for objects
            self.add_info("<b>Applied for</b>:\n")
            for idx, obj in enumerate(self.sim.objects):
                if obj.name == name:
                    self.add_info("  " + self.fmt_hl_obj(obj.idx, True) + "\n")
        return self.path_std_items(path, 1, "Cast", "cast", "obj", 
            self.sim.casts, self.sim.castsord, 0, info)

    def path_msgs(self, path):
        if self.sim is None:
            return self.path_default([])
        self.switch_view(0)
        def upd_msgs():
            path = self.curr_path
            msg = None
            if len(path) > 1:
                # index
                self.select_lb_item(path[1])
                try:
                    msg = self.sim.msgs[path[1]]
                except:
                    pass
            else:
                self.select_lb_item(None)
            # display
            sm = self.gl_state.get("msgs.sort", 0)
            if msg:
                sm = -1
            self.upd_toolgrp(self.curr_state["btnsort"], sm)
            self.clear_info()
            if not msg:
                if len(path) > 1:
                    self.add_info("<b>Message</b> \"{}\" not found\n\n".format(
                        path[1]))
                self.add_info("Select <b>message</b> from list\n\n")
                # wav
                lst = []
                for idx, msg in enumerate(self.sim.msgs):
                    if sm == 0:
                        k = msg.msg_wav
                    elif sm == 1:
                        k = idx
                    else:
                        k = msg.name
                    lst.append((k, msg.msg_wav, idx, msg.name))
                lst.sort()
                fmtlen = fmt_dec_len(len(lst))
                for _, wav, idx, capt in lst:
                    self.add_info("  " + fmt_hl_len("/msgs/{}".format(idx), 
                        "{}".format(idx), fmtlen))
                    self.add_info(" - {} - {}\n".format(
                        self.fmt_hl_file("speech{}/{}".format(
                        self.sim.curr_part, wav), wav), capt))
            else:
                # msg info
                self.add_info("<b>Message</b>: {}\n".format(path[1]))
                self.add_info("  wav:    {}\n".
                        format(self.fmt_hl_file("speech{}/{}".format(
                            self.sim.curr_part, msg.msg_wav), msg.msg_wav)))
                self.add_info("  object: " + self.fmt_hl_obj(msg.obj.idx, 
                    True) + "\n")
                self.add_info("  arg2:   {a} (0x{a:X})\n".format(
                    a = msg.msg_arg2))
                self.add_info("  arg3:   {a} (0x{a:X})\n".format(
                    a = msg.msg_arg3))
                self.add_info("\n{}\n".format(hlesc(msg.name)))
                if self.tran:
                    self.add_info("\n<i>Translated:</i>\n{}\n".\
                        format(hlesc(self._t(msg.name, "msg"))))
                self.add_info("\n<b>Used by dialog groups</b>:\n")
                for grp in self.sim.dlgs:
                    for act in grp.acts:
                        for dlg in act.dlgs:
                            for op in dlg.ops:
                                if not op.msg: continue
                                if op.msg.idx == msg.idx and op.opcode == 7:
                                    self.add_info("  " + 
                                        self.fmt_hl_dlg(grp.idx, True) + "\n")
        
        if self.last_path[:1] != ("msgs",):
            self.update_gui("Messages ({})".format(len(self.sim.msgs)))
            for idx, msg in enumerate(self.sim.msgs):
                capt = msg.name
                if self.tran:
                    capt = self._t(msg.name, "msg")
                if len(capt) > 40:
                    capt = capt[:40] + "|"
                self.insert_lb_act("{} - {}".format(msg.idx, capt),
                    ["msgs", idx], idx)
            self.curr_state["btnsort"] = self.add_toolgrp("Sort by", 
                "msgs.sort", {0: "wav", 1: "order", 2: "text"}, upd_msgs)
        # change
        upd_msgs()
        return True

    def path_dlgs(self, path):
        if self.sim is None:
            return self.path_default([])
        self.switch_view(0)
        if self.last_path[:1] != ("dlgs",):
            self.update_gui("Dialog groups ({})".format(len(self.sim.dlgs)))
            for grp in self.sim.dlgs:
                self.insert_lb_act("{} (0x{:X})".format(grp.idx, grp.idx),
                    ["dlgs", grp.idx], grp.idx)

        # change
        grp = None
        if len(path) > 1:
            # index
            self.select_lb_item(path[1])
            try:
                grp = self.sim.dlg_idx[path[1]]
            except:
                pass
        else:
            self.select_lb_item(None)
        # display
        self.clear_info()
        if not grp:
            if len(path) > 1:
                self.add_info("<b>Dialog</b> \"{}\" not found\n\n".format(
                    path[1]))
            self.add_info("Select <b>dialog group</b> from list\n")
        else:
            # grp info
            self.add_info("<b>Dialog group</b>: {} (0x{:X})\n".format(\
                grp.idx, grp.idx))
            self.add_info("  arg1: {a} (0x{a:X})\n\n".format(a = grp.grp_arg1))
            self.add_info("<b>Dialog handlers<b>: {}\n".format(len(grp.acts)))
            fmtga = "  " + fmt_dec(len(grp.acts)) + \
                ") <u>on {} {} 0x{:X} 0x{:X}</u>, dlgs: {}{}\n"
            for idx, act in enumerate(grp.acts):
                self.add_info(fmtga.format(idx, self.fmt_opcode(act.opcode), 
                        self.fmt_hl_obj(act.ref), act.arg1, act.arg2, \
                        len(act.dlgs), self.fmt_cmt(" // " + 
                            self.fmt_hl_obj(act.ref, True))))
                fmtad = "    " + fmt_dec(len(act.dlgs)) + \
                    ") <i>0x{:X} 0x{:X}</i>, ops: {}\n"
                for didx, dlg in enumerate(act.dlgs):
                    self.add_info(fmtad.format(didx, dlg.arg1, dlg.arg2, 
                        len(dlg.ops)))
                    # scan for used adreses
                    usedadr = []
                    for op in dlg.ops:
                        if op.opcode == 0x3 or \
                            op.opcode == 0x4: # GOTO or MENURET
                            if op.ref not in usedadr:
                                usedadr.append(op.ref)
                    if len(usedadr) > 0:
                        usedadr.append(dlg.op_start)
                    usedmenu = {}
                    usedcase = {}
                    for oidx, op in enumerate(dlg.ops):
                        cmt = ""
                        opref = "0x{:X}".format(op.ref)
                        opcode = self.fmt_dlgop(op.opcode)
                        if op.pos in usedadr:
                            self.add_info("      <i>label_{:X}:</i>\n".format(
                                op.pos))
                        if op.opcode == 0x1: # BREAK
                            if op.pos in usedcase:
                                if len(usedadr) > 0:
                                    cmt = self.fmt_cmt(" // end select <i>"\
                                        "label_{:X}</i>, case=0x{:}"\
                                        "".format(*usedcase[op.pos]))
                                else:
                                    cmt = self.fmt_cmt(" // end "\
                                        "select case=0x{:}".\
                                        format(usedcase[op.pos][1]))
                        elif op.opcode == 0x2 or op.opcode == 0x8: # MENU or CIRCLE
                            cmt = " // select "
                            doarr = []
                            docurr = []
                            sellen = op.ref % 0x100
                            skiptobrk = False
                            menuactstart = None
                            for oidx2, op2 in enumerate(dlg.ops[oidx + 1:]):
                                if op2.opcode == 0x1: # BREAK
                                    usedcase[op2.pos] = (op.pos, len(doarr))
                                    doarr.append(docurr)
                                    skiptobrk = False
                                    if len(doarr) == sellen:
                                        if op.opcode == 0x2:
                                            menuactstart = oidx2 + oidx + 2
                                        break
                                    docurr = []
                                elif op2.opcode == 0x7 and not skiptobrk: # PLAY
                                    docurr.append(self.fmt_hl_msg(op2.ref))
                                else:
                                    docurr = ["complex"]
                            if len(doarr) < sellen:
                                cmt = " // {} select broken, "\
                                    "required={}, got={}".\
                                    format(opcode, sellen, len(doarr))
                            else:
                                cmt += ",".join(["+".join(x) for x in doarr])
                            cmt = self.fmt_cmt(cmt)
                            if menuactstart is not None:
                                for oidx2, op2 in enumerate(dlg.ops[\
                                        menuactstart:menuactstart + sellen]):
                                    usedmenu[op2.pos] = (op.pos, oidx2)
                        elif op.opcode == 0x3 or \
                            op.opcode == 0x4: # GOTO or MENURET
                            opref = "<i>label_{:X}</i>".format(op.ref)
                            if op.pos in usedmenu:
                                cmt = self.fmt_cmt(" // action menu=<i> "\
                                    "label_{:X}</i>, case=0x{:}".\
                                    format(*usedmenu[op.pos]))
                        elif op.opcode == 0x7:
                            opcode = "PLAY"
                            if op.msg:
                                opref = self.fmt_hl_msg(op.ref)
                                objref = self.fmt_hl_obj(op.msg.obj.idx)
                                cmt = self.fmt_cmt(" // obj={}, msg={}".\
                                    format(objref, 
                                        self.fmt_hl_msg(op.ref, True)))
                        
                        oparg = " 0x{:X} ".format(op.arg)
                        if (op.opcode == 0x1 or op.opcode == 0x6) and \
                                op.arg == 0 and op.ref == 0:
                            oparg = ""
                            opref = ""
                        self.add_info("        {}{}{}{}\n".\
                            format(opcode, oparg, opref, cmt))

            def usedby(lst):
                for idx, rec in enumerate(lst):
                    ru = False
                    for act in rec.acts:
                        if ru: break
                        for op in act.ops:
                            if op.op_code == 0x11 and \
                                    op.op_ref == grp.idx: # DIALOG 
                                self.add_info("  " + 
                                    self.fmt_hl_obj_scene(rec.idx, True) + "\n")
                                ru = True
                                break
                            #print(op_id, op_code, op_res, op4, op5)

            self.add_info("\n\n<b>Used by objects</b>:\n")
            usedby(self.sim.objects)
            self.add_info("\n<b>Used by scenes</b>:\n")
            usedby(self.sim.scenes)
        return True
        
    def path_opcodes(self, path):
        if self.sim is None:
            return self.path_default([])
        self.switch_view(0)
        keys = None
        def keyslist():
            opstat = {} # opcodes count
            acstat = {} # handlers count
            dastat = {} # dialog handlers count
            keys = list(petka.OPCODES.keys())
            for rec in self.sim.objects + self.sim.scenes:
                for act in rec.acts:
                    acstat[act.act_op] = acstat.get(act.act_op, 0) + 1
                    if act.act_op not in keys:
                        keys.append(act.act_op)
                    for op in act.ops:
                        opstat[op.op_code] = opstat.get(op.op_code, 
                            0) + 1
                        if op.op_code not in keys:
                            keys.append(op.op_code)
            for grp in self.sim.dlgs:
                for act in grp.acts:
                    dastat[act.opcode] = dastat.get(act.opcode, 0) + 1
                    if act.opcode not in keys:
                        keys.append(act.opcode)
            keys.sort()
            return keys, opstat, acstat, dastat
        if self.last_path[:1] != ("opcodes",):
            # calc statistics
            keys, opstat, acstat, dastat = keyslist()
            self.update_gui("Opcodes ({})".format(len(keys)))
            for key in keys:
                self.insert_lb_act("{} - {}".format(key, self.fmt_opcode(key, 
                    True)), ["opcodes", key], key)
        # change
        opcode = None
        if len(path) > 1:
            # index
            self.select_lb_item(path[1])
            try:
                opcode = path[1]
            except:
                pass
        else:
            self.select_lb_item(None)
        # display
        self.clear_info()
        if not opcode:
            if len(path) > 1:
                self.add_info("<b>Opcode </b> \"{}\" not found\n\n".format(
                    path[1]))
            self.add_info("<b>Opcodes</b>\n\n")
            # display
            if not keys:
                keys, opstat, acstat, dastat = keyslist()
            for key in keys:
                opname = self.fmt_opcode(key)
                msg = "  {:2} (0x{:02X})".format(key, key,
                    opname)
                mcnt = len(msg)
                msg += " - {}".format(fmt_hl("/opcodes/{}".format(
                    key), opname))
                mcnt += len(self.fmt_opcode(key, True))    
                while mcnt < 23:
                    msg += " "
                    mcnt += 1
                msg += "{:4d}  {:4d}  {:4d}".format(
                    opstat.get(key, 0),
                    acstat.get(key, 0),
                    dastat.get(key, 0))
                self.add_info(msg + "\n")
        else:
            # grp info
            self.add_info("<b>Opcode {}</b>\n\n".format(
                self.fmt_opcode(opcode)))
            ops = []
            acts = []
            dacts = []
            for rec in self.sim.objects + self.sim.scenes:
                for aidx, act in enumerate(rec.acts):
                    if act.act_op == opcode:
                        acts.append([rec.idx, aidx])
                    for oidx, op in enumerate(act.ops):
                        if op.op_code == opcode:
                            ops.append([rec.idx, aidx, oidx])
            for grp in self.sim.dlgs:
                for aidx, act in enumerate(grp.acts):
                    if act.opcode == opcode and act.ref not in dacts:
                        dacts.append([act.ref, grp.idx, aidx])
            # display
            if len(ops) == 0:
                self.add_info("<i>Not used in scripts</i>\n\n")
            else:            
                self.add_info("<i>Used in scripts</i>: {}\n".format(len(ops)))
                fmtops = "  " + fmt_dec(len(ops)) + \
                    ") obj={}, act={}, op={} {}\n"
                for idx, (obj_idx, aidx, oidx) in enumerate(ops):
                    self.add_info(fmtops.format(
                        idx, self.fmt_hl_obj_scene(obj_idx, False), aidx, oidx,
                        self.fmt_cmt("// " + self.fmt_hl_obj_scene(obj_idx, 
                        True))))
                self.add_info("\n")  

            if len(acts) == 0:
                self.add_info("<i>Not used in handlers</i>\n\n")
            else:            
                self.add_info("<i>Used in handlers</i>: {}\n".format(len(acts)))
                fmtacts = "  " + fmt_dec(len(acts)) + \
                    ") obj={}, act={} {}\n"
                for idx, (obj_idx, aidx) in enumerate(acts):
                    self.add_info(fmtacts.format(
                        idx, self.fmt_hl_obj_scene(obj_idx, False), aidx, 
                        self.fmt_cmt("// " + self.fmt_hl_obj_scene(obj_idx, 
                        True))))
                self.add_info("\n")  

            if len(dacts) == 0:
                self.add_info("<i>Not used in dialog handlers</i>\n\n")
            else:            
                self.add_info("<i>Used in dialog handlers</i>: {}\n".format(
                    len(dacts)))
                fmtdacts = "  " + fmt_dec(len(dacts)) + \
                    ") obj={}, group=<a href=\"/dlgs/{}\">{}</a>, act={} {}\n"
                for idx, (obj_idx, gidx, aidx) in enumerate(dacts):
                    self.add_info(fmtdacts.format(
                        idx, self.fmt_hl_obj_scene(obj_idx, False), gidx, gidx, 
                        aidx, self.fmt_cmt("// " + self.fmt_hl_obj_scene(
                        obj_idx, True))))
                self.add_info("\n")  
        return True

    def path_dlgops(self, path):
        if self.sim is None:
            return self.path_default([])
        self.switch_view(0)
        keys = None
        def keyslist():
            dlstat = {} # dialog opcodes count
            keys = list(petka.DLGOPS.keys()) + [5, 9]
            for grp in self.sim.dlgs:
                for act in grp.acts:
                    for dlg in act.dlgs:
                        for op in dlg.ops:
                            dlstat[op.opcode] = dlstat.get(op.opcode, 0) + 1
                            if op.opcode not in keys:
                                keys.append(op.opcode)
            keys.sort()
            return keys, dlstat
        if self.last_path[:1] != ("dlgops",):
            # calc statistics
            keys, dlstat = keyslist()
            self.update_gui("Dialog opcodes ({})".format(len(keys)))
            for key in keys:
                self.insert_lb_act("{} - {}".format(key, self.fmt_dlgop(key, 
                    True)), ["dlgops", key], key)
        # change
        opcode = None
        if len(path) > 1:
            # index
            self.select_lb_item(path[1])
            try:
                opcode = path[1]
            except:
                pass
        else:
            self.select_lb_item(None)
        # display
        self.clear_info()
        if not opcode:
            if len(path) > 1:
                self.add_info("<b>Dialog opcode </b> \"{}\" not found\n\n".\
                    format(path[1]))
            self.add_info("<b>Dialog opcodes</b>\n\n")
            # display
            if not keys:
                keys, dlstat = keyslist()
            for key in keys:
                opname = self.fmt_dlgop(key)
                msg = "  {:2} (0x{:02X})".format(key, key, opname)
                mcnt = len(msg)
                msg += " - {}".format(fmt_hl("/dlgops/{}".format(
                    key), opname))
                mcnt += len(self.fmt_dlgop(key, True))    
                while mcnt < 20:
                    msg += " "
                    mcnt += 1
                msg += "{:4d}".format(dlstat.get(key, 0))
                self.add_info(msg + "\n")
        else:
            # grp info
            self.add_info("<b>Dialog opcode {}</b>\n\n".format(
                self.fmt_dlgop(opcode)))
            dls = []
            for grp in self.sim.dlgs:
                for aidx, act in enumerate(grp.acts):
                    for didx, dlg in enumerate(act.dlgs):
                        for oidx, op in enumerate(dlg.ops):
                            if op.opcode == opcode:
                                dls.append([act.ref, grp.idx, aidx, didx, oidx])
            # display
            if len(dls) == 0:
                self.add_info("<i>Not used in dialogs</i>\n\n")
            else:            
                self.add_info("<i>Used in dialogs</i>: {}\n".format(len(dls)))
                fmtdls = "  " + fmt_dec(len(dacts)) + \
                    ") obj={}, group=<a href=\"/dlgs/{}\">{}" + \
                        "</a>, act={}, dlg={}, op={} {}\n"
                for idx, (obj_idx, gidx, aidx, didx, oidx) in enumerate(dls):
                    self.add_info(fmtdls.format(
                        idx, self.fmt_hl_obj_scene(obj_idx, False), gidx, gidx, 
                        aidx, didx, oidx, self.fmt_cmt("// " + 
                        self.fmt_hl_obj_scene(obj_idx, True))))
                self.add_info("\n")  
        return True

    def fmt_hl_file(self, fn, capt = None):
        fnl = fn.lower().replace("\\", "/")
        capt = capt or fn
        fid = urllib.parse.quote_plus(fnl)
        return "<a href=\"/files/{}\">{}</a>".format(fid, hlesc(capt))                   
        
    def path_stores(self, path):
        if self.strfm is None:
            return self.path_default([])
        def upd_strs():
            path = self.curr_path
            # change
            stid = None
            if len(path) > 1:
                # index
                self.select_lb_item(path[1])
                try:
                    stid = path[1]
                except:
                    pass
            else:
                self.select_lb_item(None)
            # display
            self.clear_info()
            sm = self.gl_state.get("strs.sortfiles", 0)
            if stid is None:
                sm = -1
            self.upd_toolgrp(self.curr_state["btnsort"], sm)
            self.curr_state["btnext"].config(state = tkinter.DISABLED)
            if stid is None:
                self.add_info("<b>Stores</b>\n\n")
                fmt = "  " + fmt_dec(len(self.strfm.strfd)) + \
                    ") <a href=\"/strs/{}\">{}</a> (tag={})\n"
                for idx, st in enumerate(self.strfm.strfd):
                    self.add_info(fmt.format(idx + 1, idx, st[1], st[2]))
            else:
                if stid >= len(self.strfm.strfd):
                    self.add_info("<b>Store</b> \"{}\" not found\n\n".\
                        format(path[1]))
                    return
                self.curr_state["btnext"].config(state = tkinter.NORMAL)
                _, name, tag, strlst = self.strfm.strfd[stid]
                self.add_info("<b>Store</b>: {}\n".format(name))
                flnk = "{}".format(len(strlst))
                if len(strlst):
                    flnk = self.fmt_hl_file(strlst[0][0], flnk)
                self.add_info("  Files: {}, Tag: {}\n\n".format(flnk, tag))
                
                lst = []
                for idx, (fname, _, _, _) in enumerate(strlst):
                    if sm == 0:
                        k = idx
                    else:
                        k = fname.lower().replace("\\", "/")
                    lst.append((k, idx, fname))
                lst.sort()
                fmt = "  " + fmt_dec(len(lst)) + ") {}\n"
                for _, idx, fname in lst:
                    self.add_info(fmt.format(idx + 1, 
                        self.fmt_hl_file(fname)))
            
        self.switch_view(0)
        keys = None
        if self.last_path[:1] != ("strs",):
            # calc statistics
            self.update_gui("Stores ({})".format(len(self.strfm.strfd)))
            for idx, st in enumerate(self.strfm.strfd):
                self.insert_lb_act("{}".format(st[1]), ["strs", idx], idx)
            def ext_str():
                stid = None
                try:
                    stid = self.curr_path[1]
                except:
                    pass
                if stid is None:
                    self.clear_info()
                    self.add_info("<b>Select store</b>\n")
                    return
                # extract to folder
                sdir = filedialog.askdirectory(parent = self,
                    title = "Select folder for extract", 
                    initialdir = self.strfm.root, mustexist = True)
                if not sdir: return
                # extract store to sdir
                fd, _, _, strlst = self.strfm.strfd[stid]
                self.clear_info()
                for fname, _, pos, ln in strlst:
                    try:
                        self.add_info("  \"{}\" - {} bytes\n".
                            format(hlesc(fname), ln))
                        np = sdir
                        for elem in fname.split("/"):
                            np = os.path.join(np, elem)
                        # check folder
                        bn = os.path.dirname(np)
                        if not os.path.exists(bn):
                            os.makedirs(bn)
                        f = open(np, "wb")
                        fd.seek(pos)
                        f.write(fd.read(ln))
                        f.close()
                    except:
                        self.add_info("Error extracting \"{}\"\n\n{}".\
                            format(hlesc(fname), hlesc(traceback.format_exc())))
                        return
            self.curr_state["btnext"] = self.add_toolbtn("Extract STR", ext_str)
            self.curr_state["btnsort"] = self.add_toolgrp("Sort by", 
                "strs.sortfiles", {0: "order", 1: "filename"}, upd_strs)
        upd_strs()
        return True

    def desc_files(self, path):
        # this part can be internationalized
        if len(path) > 1:
            fnl = urllib.parse.unquote(path[1])
            return "File \"{}\"".format(fnl)
        return "Files"

    def path_files(self, path):
        if self.strfm is None:
            return self.path_default([])
        def upd_files():
            path = self.curr_path
            fid = None
            if len(path) > 1:
                # normalize fn
                fnl = urllib.parse.unquote(path[1]).replace("\\","/").lower()
                fid = urllib.parse.quote_plus(fnl)
                # index
                self.select_lb_item(fid)
            else:
                self.select_lb_item(None)
            self.clear_info()
            sm = self.gl_state.get("files.sort", 0)
            if fid is not None:
                sm = -1
            self.upd_toolgrp(self.curr_state["btnsort"], sm)
            if fid is None:
                self.add_info("<b>Files in all stores</b>\n\n")
                lst = []
                for idx, fn in enumerate(self.strfm.strtableord):
                    if sm == 0:
                        k = idx
                    else:
                        k = fn.lower().replace("\\", "/")
                    lst.append((k, idx, fn))
                lst.sort()
                fmt = "  " + fmt_dec(len(lst)) + ") {}\n"
                for _, idx, fn in lst:
                    #stid, _, _ = self.strfm.strtable[fn]
                    self.add_info(fmt.format(
                        idx + 1, self.fmt_hl_file(fn)))
            else:
                try:
                    self.strfm.read_file(fnl)
                except:
                    self.add_info("<b>File</b> \"{}\" not found\n\n".\
                        format(hlesc(fnl)))
                    return
                self.add_info("<b>File</b>: {}\n\n".format(fnl))
                    
                # search in loaded stores
                if fnl in self.strfm.strtable:
                    # in store
                    stid, pos, ln = self.strfm.strtable[fnl]
                    self.add_info("  Store: <a href=\"/strs/{}\">{}</a>\n".format(
                        stid, self.strfm.strfd[stid][1]))
                    self.add_info("  Pos: {} (0x{:x}), Len: {} (0x{:x})\n".format(
                        pos, pos, ln, ln))
                else:
                    # on disk
                    self.add_info("  Loaded from disk\n")

                if self.sim:
                    wascapt = False
                    for resid in self.sim.resord:
                        resfn = self.sim.res[resid].lower().replace("\\", "/")
                        if resfn == fnl:
                            if not wascapt:
                                self.add_info("\n<b>Used in resources</b>:\n")
                                wascapt = True
                            self.add_info("  {} - <a href=\"/res/all/{}\">"\
                                "{}</a>\n".format(resid, resid, 
                                hlesc(self.sim.res[resid])))
                    wavpref = "speech{}/".format(self.sim.curr_part)
                    if fnl[-4:] == ".wav" and fnl.startswith(wavpref):
                        wascapt = False
                        for idx, msg in enumerate(self.sim.msgs):
                            if fnl == wavpref + msg.msg_wav.lower():
                                if not wascapt:
                                    self.add_info("\n<b>Used in messages</b>:"
                                        "\n")
                                    wascapt = True
                                    self.add_info("  {}\n".format(
                                        self.fmt_hl_msg(idx, True)))

                grp = [
                    [".leg", ".off", ".msk", ".flc"],
                    [".bmp", ".cvx"]
                ]
                sg = None
                for g in grp:
                    if fnl[-4:] in g:
                        sg = g
                if sg:
                    self.add_info("\n<b>Related file(s)</b>:\n")
                    rel = []
                    for ext in sg:
                        if ext == fnl[-4:]: continue
                        if self.strfm.exists(fnl[:-4] + ext):
                            self.add_info("  {}\n".format(self.fmt_hl_file(
                                fnl[:-4] + ext)))
                # special files
                fns = fnl.split("/")
                last = ""
                while len(fns) > 0:
                    if fns[-1:] == [""]:
                        continue
                    last = fns[-1:][0]
                    break
                sa = None
                if last in ["script.dat", "backgrnd.bg", "bgdata.dat", "bgedit.bg"]:
                    sa = ["/objs", "/scenes", "/opcodes"]
                if last == "cast.ini":
                    sa = ["/objs", "/casts"]
                if last == "names.ini":
                    sa = ["/objs", "/names"]
                if last == "invntr.txt":
                    sa = ["/objs", "/invntr"]
                if last == "bgs.ini":
                    sa = ["/scenes", "/bgs"]
                if last in ["dialogue.fix", "dialogue.lod"]:
                    sa = ["/dlgs", "/msgs", "/dlgops"]
                if last == "resource.qrc":
                    sa = ["/res", "/files"]
                if last == "parts.ini":
                    sa = ["/parts"]
                if last[:4] == "disk" and last[-3:] == ".id":
                    sa = ["/parts"]
                if sa:
                    self.add_info("\n<b>See also</b>:\n")
                    for p in sa:
                        self.add_info("  " + fmt_hl(p, self.desc_path(p)) 
                            + "\n")
                        
                if fnl[-4:] in [".leg", ".off"]:
                    legf = petka.LEGLoader()
                    legf.load_data(self.strfm.read_file_stream(fnl))
                    self.add_info("\n<b>LEG/OFF data</b>: {} frame(s)\n".format(
                        len(legf.coords)))
                    fmt = "  " + fmt_dec(len(legf.coords)) + ") {}, {}\n"
                    for idx, (x, y) in enumerate(legf.coords):
                        self.add_info(fmt.format(idx + 1, x, y))
                        
                if fnl[-4:] == ".msk":
                    mskf = petka.MSKLoader()
                    mskf.load_data(self.strfm.read_file_stream(fnl))
                    self.add_info("\n<b>MSK data</b>: {} record(s)\n".format(
                        len(mskf.rects)))
                    self.add_info("  bound: {}, {} - {}, {}\n".format(
                        *mskf.bound))
                    fmt = "  " + fmt_dec(len(mskf.rects)) + \
                        ") stamp = {}, {} rect(s)\n"
                    for idx, (stamp, rs) in enumerate(mskf.rects):
                        self.add_info(fmt.format(idx + 1, stamp, len(rs)))
                        fmtr = "    " + fmt_dec(len(rs)) + ") {}, {} - {}, {}\n"
                        for idxr, r in enumerate(rs):
                            self.add_info(fmtr.format(idxr + 1, *r))
                        
                if fnl[-4:] == ".flc":
                    flcf = petka.FLCLoader()
                    flcf.load_info(self.strfm.read_file_stream(fnl))
                    if flcf.image:
                        # PIL
                        self.add_info("\n<b>FLC data</b> (pil)\n")
                        self.add_info("  Mode:   {}\n  Size:   {}x{}\n"
                            "  Frames: {}\n  Delay:  {}".\
                            format(flcf.image.mode, \
                                flcf.image.size[0], flcf.image.size[1],
                                flcf.frame_num, flcf.image.info["duration"]))
                    else:    
                        self.add_info("\n<b>FLC data</b> (internal)\n")
                        self.add_info("  Mode:   P\n  Size:   {}x{}\n"\
                            "  Frames: {}\nDelay: {}".\
                            format(flcf.width, flcf.height, \
                                flcf.frame_num, flcf.delay))
                        
        self.switch_view(0)
        keys = None
        if self.last_path[:1] != ("files",):
            # calc statistics
            self.update_gui("Files ({})".format(len(self.strfm.strtable)))
            for idx, fn in enumerate(self.strfm.strtableord):
                fnl = fn.lower().replace("\\", "/")
                fnl = urllib.parse.quote_plus(fnl)
                self.insert_lb_act(fn, ["files", fnl], fnl)
            self.curr_state["btnsort"] = self.add_toolgrp("Sort by", 
                "files.sort", {0: "order", 1: "filename"}, upd_files)
        upd_files()
        return True

    def path_save(self, path):
        if self.sim is None:
            return self.path_default([])
            
        def upd_save():
            path = self.curr_path
            fid = None
            self.switch_view(0)
            if self.save is None:
                self.add_info("<b>Saved state:not loaded</b>\n\n")
                
            if path == ("save",):
                path = ("save", "info")
            if path[1] == "shot":
                self.select_lb_item("shot")
                self.main_image = \
                    self.make_image(self.save.shot)
                self.switch_view(1)
                self.update_canvas()
            elif path[1] == "info":
                self.clear_info()
                self.add_info("<b>Saved state:</b>\n\n")
                self.add_info("  part:  {}, chapter {}\n".format(
                    self.save.part, self.save.chap))
                self.add_info("  stamp: " + hlesc(self.save.stamp) + "\n")
                self.add_info("  scene: " + hlesc(self.save.scene) + "\n")
            else:
                self.select_lb_item("info")
                        
        if self.last_path[:1] != ("save",):
            # calc statistics
            self.update_gui("Save")
            self.insert_lb_act("Info", ["save"], "info")
            self.insert_lb_act("Screenshot", ["save", "shot"], "shot")
        upd_save()
        return True
            
            
    def path_test(self, path):
        def display_page():
            item = None
            path = self.curr_path
            if len(path) > 2:
                item = path[2]
            self.clear_info()
            sm = self.gl_state.get("test.info.mode", 0)
            if item is None:
                sm = -1
            self.upd_toolgrp(self.curr_state["gbtns"], sm)
            if item is None:
                self.switch_view(0)
                self.add_info("Select item " + path[1])
            else:
                if path[1] == "image":
                    self.switch_view(1)
                    self.main_image = tkinter.PhotoImage(file = "img/splash.gif")
                elif path[1] == "info":
                    self.switch_view(0)
                    self.add_info("Information panel for {}\n".format(path))
                    self.add_info("Local mode {}\n".format(
                        self.curr_state.get("mode", None)))
                    self.add_info("Global mode {}\n".format(
                        self.gl_state.get("test.info.mode", None)))
                    for i in range(100):
                        self.add_info("  Item {}\n".format(i))
            
        if self.last_path[:1] != ("test",):
            self.update_gui("Test {}".format(path[1]))
            self.insert_lb_act("Outline", [])
            self.insert_lb_act("-", None)
            for i in range(15):
                self.insert_lb_act("{} #{}".format(path[1], i), 
                    path[:2] + (i,), i)
            # create mode buttons
            def sw_mode1():
                print("Mode 1")
                self.curr_state["mode"] = 1
                self.curr_state["btn1"].config(state = tkinter.DISABLED)
                self.curr_state["btn2"].config(state = tkinter.NORMAL)
                display_page()
            def sw_mode2():
                print("Mode 2")
                self.curr_state["mode"] = 2
                self.curr_state["btn1"].config(state = tkinter.NORMAL)
                self.curr_state["btn2"].config(state = tkinter.DISABLED)
                display_page()
            self.curr_state["btn1"] = self.add_toolbtn("Mode 1", sw_mode1)
            self.curr_state["btn2"] = self.add_toolbtn("Mode 2", sw_mode2)
            # we store buttons in local state
            self.curr_state["gbtns"] = self.add_toolgrp(None, "test.info.mode",
                {0: "mode 1", 1: "mode 2", 2: "mode 3"}, display_page)

        # change
        item = None
        if len(path) > 2:
            # index
            self.select_lb_item(path[2])
            try:
                item = path[2]
            except:
                pass
        else:
            self.select_lb_item(None)
        # display
        display_page()
        return True

    def path_about(self, path):
        self.switch_view(0)
        self.update_gui("About")
        self.insert_lb_act("Outline", [])
        self.clear_info()
        self.add_info("Welcome to <b>Petka 1 & 2 resource explorer</b>\n\n")
        self.add_info("  " + APPNAME + " " + VERSION + "\n")
        self.add_info("  romiq.kh@gmail.com\n")
        self.add_info("  https://bitbucket.org/romiq/p12simtran\n")
        self.add_info("\n")
        self.path_info_outline()
        return True

    def path_support(self, path):
        self.switch_view(0)
        self.update_gui("Support")
        self.insert_lb_act("Outline", [])
        self.clear_info()
        self.add_info("" + APPNAME + " " + VERSION + "\n")
        self.add_info("=" * 40 + "\n")
        self.add_info("<b>App folder</b>:   {}\n".format(
            hlesc(self.app_path)))
        self.add_info("<b>Game folder</b>:  {}\n".format(
            hlesc(self.last_fn)))
        self.add_info("<b>Translation</b>:  ")
        if not polib:
            self.add_info("<i><u>polib</u> not found</i>\n")
        else:
            if not self.tran:
                self.add_info("<i>no tranlation file</i>\n")
            else:
                self.add_info(hlesc(self.tran_fn) + "\n")
                
        self.add_info("<b>Engine</b>:       ")
        if not self.sim:
            self.add_info("<i>not initialized</i>\n")
        else:
            self.add_info("<i>works</i>\n\n")
            self.add_info("  <b>Path</b>:    {}\n".format(
                hlesc(self.sim.curr_path)))
            self.add_info("  <b>Start</b>:   {}.{}\n".format(
                self.sim.start_part, self.sim.start_chap))
            self.add_info("  <b>Speech</b>:  {}\n".format(
                hlesc(self.sim.curr_speech)))
            self.add_info("  <b>Disk ID</b>: {}\n\n".format(
                hlesc(self.sim.curr_diskid)))

        self.add_info("<b>File manager</b>: ")
        if not self.strfm:
            self.add_info("<i>not initialized</i>\n")
        else:
            self.add_info("<i>works</i>\n\n")
            self.add_info("  <b>Path</b>: {}\n\n".format(
                hlesc(self.strfm.root)))

        self.add_info("<b>Saved state</b>: ")
        if not self.strfm:
            self.add_info("<i>not loaded</i>\n")
        else:
            self.add_info("<i>loaded</i>\n\n")

        if self.sim or self.strfm:
            self.path_info_outline()

        return True
            
    def desc_help(self, path):
        if path == ("help",):
            path = ("help", "index")
        if path == ("help", "index"):
            return "Index"
        return "Help for " + self.desc_path(path[1])
            
    def path_help(self, path):
        self.switch_view(0)
        if path == ("help",):
            path = ("help", "index")
        if self.last_path[:1] != ("help",):
            self.update_gui("Help")
            # build help index
            lfn = os.path.join(self.app_path, "help", "list")
            f = open(lfn, "rb")
            try:
                for item in f.readlines():
                    item = item.decode("UTF-8").strip()
                    if not item: continue
                    try:
                        hf = open(os.path.join(self.app_path, 
                            "help", item + ".txt"), "rb")
                        try:
                            for line in hf.readlines():
                                line = line.decode("UTF-8").strip()                    
                                break
                        finally:
                            hf.close()
                    except:
                        line = item                    
                    self.insert_lb_act(line, ["help", item], item)
            finally:
                f.close()

            self.insert_lb_act("-", None)
            self.insert_lb_act("Outline", [])

        # change
        if len(path) > 1:
            # parts
            self.select_lb_item(path[1])
            self.clear_info()
            hfn = os.path.join(self.app_path, "help", path[1] + ".txt")
            try:
                hf = open(hfn, "rb")
                try:
                    for idx, line in enumerate(hf.readlines()):
                        line = line.decode("UTF-8").rstrip()                    
                        if idx == 0:
                            self.add_info("<b>" + line + "</b>\n")
                        else:                                        
                            self.add_info(line + "\n")
                finally:
                    hf.close()
            except:
                self.add_info("Error loading \"{}\" \n\n{}".\
                    format(hlesc(hfn), hlesc(traceback.format_exc())))
        else:
            self.select_lb_item(None)

        return True
        
    def path_info(self, path):
        self.switch_view(0)
        if self.last_path[:1] != ("info",):
            self.update_gui("Info")
            self.insert_lb_act("Opcodes", ["info", "opcodes"], "opcodes")
            self.insert_lb_act("Dialog opcodes", ["info", "dlgops"], "dlgops")
        # change
        name = None
        if len(path) > 1:
            # lb
            self.select_lb_item(path[1])
            name = path[1]
        else:
            self.select_lb_item(None)
        # display
        self.clear_info()
        if not name:
            self.add_info("Select <b>info</b> from list\n")
        else:
            # info
            if name == "opcodes":
                self.add_info("<b>Opcodes<b>\n\n")
                k = list(petka.OPCODES.keys())
                k.sort()
                for key in k:
                    self.add_info("  {} (0x{:X}) - {}\n".format(key, key,
                        petka.OPCODES[key][0])) 
            elif name == "dlgops":
                self.add_info("<b>Dialog opcodes<b>\n\n")
                k = list(petka.DLGOPS.keys())
                k.sort()
                for key in k:
                    self.add_info("  {} (0x{:X}) - {}\n".format(key, key,
                        petka.DLGOPS[key][0]))
            else: 
                self.add_info("Unknown data type \"{}\"\n".format(hlesc(name)))

        return True

    def on_open_data(self):
        ft = [\
            ('all files', '.*')]
        fn = filedialog.askopenfilename(parent = self, 
            title = "Open PARTS.INI or SCRIPT.DAT",
            filetypes = ft,
            initialdir = os.path.abspath(os.curdir))
        if not fn: return
        os.chdir(os.path.dirname(fn))
        self.clear_hist()
        if self.open_data_from(os.path.dirname(fn)):
            self.open_path("")
            self.clear_hist()
        
    def open_data_from(self, folder):
        self.last_fn = folder
        self.clear_data()
        try:
            self.sim = petka.Engine()
            self.sim.load_data(folder, "cp1251")
            self.strfm = self.sim.fman
            self.sim.open_part(0, 0)
            return True
        except:
            print("DEBUG: Error opening data")
            self.clear_data()
            self.switch_view(0)
            self.update_gui("")
            self.clear_info()
            self.add_info("Error opening \"{}\" \n\n{}".\
                format(hlesc(folder), hlesc(traceback.format_exc())))

    def on_open_str(self):
        ft = [\
            ('STR files', '.STR'),
            ('all files', '.*')]
        fn = filedialog.askopenfilename(parent = self, 
            title = "Open STR file",
            filetypes = ft,
            initialdir = os.path.abspath(os.curdir))
        if not fn: return
        os.chdir(os.path.dirname(fn))
        self.clear_hist()
        if self.open_str_from(fn):
            self.open_path("/strs")
            self.clear_hist()

    def open_str_from(self, fn):
        self.last_fn = fn
        self.clear_data()
        try:
            self.strfm = petka.FileManager(os.path.dirname(fn))
            self.strfm.load_store(os.path.basename(fn))
            return True
        except:
            print("DEBUG: Error opening STR")
            self.clear_data()
            self.switch_view(0)
            self.update_gui("")
            self.clear_info()
            self.add_info("Error opening \"{}\" \n\n{}".\
                format(hlesc(fn), hlesc(traceback.format_exc())))

    def on_open_savedat(self):
        ft = [\
            ('Save files (*.dat)', '.DAT'),
            ('all files', '.*')]
        fn = filedialog.askopenfilename(parent = self, 
            title = "Open SAVEx.DAT file",
            filetypes = ft,
            initialdir = os.path.abspath(os.curdir))
        if not fn: return
        os.chdir(os.path.dirname(osfn))
        if self.open_savedat_from(fn):
            self.open_path("/save")

    def open_savedat_from(self, fn):
        if self.sim is None:
            self.switch_view(0)
            self.update_gui("")
            self.clear_info()
            self.add_info("Open data before loading saves")  
            return
        self.save = None
        try:
            self.save = petka.SaveLoader("cp1251")
            with open(fn, "rb") as f:
                self.save.load_data(f, self.sim.curr_part, 
                    len(self.sim.objects) + len(self.sim.scenes))
                if self.save.part != self.sim.curr_part:
                    # load
                    print("DEBUG: change part {}".format(self.save.part))
                    self.sim.open_part(self.save.part, 0)
                    f.seek(0)
                    self.save.load_data(f, self.sim.curr_part, 
                        len(self.sim.objects) + len(self.sim.scenes))
            return True
        except:
            print("DEBUG: Error opening SAVEx.DAT")
            self.save = None
            self.switch_view(0)
            self.update_gui("")
            self.clear_info()
            self.add_info("Error opening \"{}\" \n\n{}".\
                format(hlesc(fn), hlesc(traceback.format_exc())))
            

    def on_tran_save(self):
        self.on_tran_save_real()

    def on_tran_save_tlt(self):
        self.on_tran_save_real(True)
        
    def on_tran_save_real(self, tlt = False):
        # save dialog
        fn = filedialog.asksaveasfilename(parent = self,
            title = "Save translate template (.pot)" + 
                " (transliterate)" if tlt else "",
            filetypes = [('PO Template', ".pot"), ('all files', '.*')],
            initialdir = os.path.abspath(os.curdir))
        if not fn: return # save canceled
        # save template
        try:
            po = polib.POFile()
            po.metadata = {
                'MIME-Version': '1.0',
                'Content-Type': 'text/plain; charset=utf-8',
                'Content-Transfer-Encoding': '8bit',
            }
            used = []
            def saveitem(text, cmt = None):
                if text in used: return
                used.append(text)
                ts = text
                if tlt:
                    ts = translit(text)
                entry = polib.POEntry(
                    msgid = text, msgstr = ts, comment = cmt)
                po.append(entry)                
            for rec in self.sim.objects:
                saveitem(rec.name, "obj_{}".format(rec.idx))
            for rec in self.sim.scenes:
                saveitem(rec.name, "scn_{}".format(rec.idx))
            for idx, name in enumerate(self.sim.namesord):
                saveitem(self.sim.names[name], 
                    "name_{}, {}".format(idx, name))
            for idx, name in enumerate(self.sim.invntrord):
                saveitem(self.sim.invntr[name],
                    "inv_{}, {}".format(idx, name))
            for idx, msg in enumerate(self.sim.msgs):
                saveitem(msg.name, 
                    "msg_{}, {} - {}".format(idx, msg.obj.idx, msg.obj.name))
            po.save(fn)
        except:
            self.switch_view(0)
            self.clear_info()
            self.add_info("Error saving \"{}\" \n\n{}".\
                format(hlesc(fn), hlesc(traceback.format_exc())))

    def on_tran_load(self):
        ft = [\
            ('PO files', '.po'),
            ('all files', '.*')]
        fn = filedialog.askopenfilename(parent = self, 
            title = "Open translation for current part",
            filetypes = ft,
            initialdir = os.path.abspath(os.curdir))
        if not fn: return
        os.chdir(os.path.dirname(fn))
        self.open_tran_from(fn)
            
    def open_tran_from(self, fn):
        self.tran_fn = fn
        try:
            po = polib.pofile(fn)
            self.tran = {"obj": {}, "scn": {}, "name": {}, "inv": {},
              "msg": {}, "_": {}}
            for tr in po.translated_entries():
                if tr.comment:
                    pref = tr.comment.split("_", 1)
                    if pref[0] in self.tran:
                        self.tran[pref[0]][tr.msgid] = tr.msgstr
                    self.tran["_"][tr.msgid] = tr.msgstr
            return True
        except:
            self.switch_view(0)
            self.clear_info()
            self.add_info("Error opening \"{}\" \n\n{}".\
                format(hlesc(fn), hlesc(traceback.format_exc())))

    def on_tran_save_lod(self):
        # save dialog
        if not self.sim: return
        if len(self.sim.msgs) == 0 or not self.tran:
            self.switch_view(0)
            self.clear_info()
            self.add_info("No messages or translations loaded")
            return        
        fn = filedialog.asksaveasfilename(parent = self,
            title = "Save DIALOGUE.LOD",
            filetypes = [('DIALOGUE.LOD', ".lod"), ('all files', '.*')],
            initialdir = os.path.abspath(os.curdir))
        if not fn: return # save canceled
        # save template
        try:
            sim2 = petka.Engine()
            sim2.init_empty("cp1251")
            for msg in self.sim.msgs:
                nmsg = petka.engine.MsgObject(msg.idx, msg.msg_wav, 
                    msg.msg_arg1, msg.msg_arg2, msg.msg_arg3)
                nmsg.name = self._t(msg.name, "msg")
                sim2.msgs.append(nmsg)
            f = open(fn, "wb")
            try:
                sim2.write_lod(f)
            finally:
                f.close()
        except:
            self.switch_view(0)
            self.clear_info()
            self.add_info("Error saving \"{}\" \n\n{}".\
                format(hlesc(fn), hlesc(traceback.format_exc())))

    def on_tran_save_names(self):
        # save dialog
        if not self.sim: return
        if len(self.sim.msgs) == 0 or not self.tran:
            self.switch_view(0)
            self.clear_info()
            self.add_info("No messages or translations loaded")
            return        
        fn = filedialog.asksaveasfilename(parent = self,
            title = "Save NAMES.INI",
            filetypes = [('NAMES.INI', ".ini"), ('all files', '.*')],
            initialdir = os.path.abspath(os.curdir))
        if not fn: return # save canceled
        # save template
        try:
            f = open(fn, "wb")
            def write(msg):
                f.write("{}\n".format(msg).encode("cp1251"))
            try:
                write("[all]")
                for name in self.sim.namesord:
                    write(name + "=" + self._t(self.sim.names[name], "name"))
            finally:
                f.close()
        except:
            self.switch_view(0)
            self.clear_info()
            self.add_info("Error saving \"{}\" \n\n{}".\
                format(hlesc(fn), hlesc(traceback.format_exc())))


def main():
    root = tkinter.Tk()
    app = App(master = root)
    argv = sys.argv[1:]
    while len(argv) > 0:
        if argv[0] == "-d": # open data
            app.start_act.append(["load", argv[1]])
            argv = argv[2:]
        elif argv[0] == "-s": # open str file
            app.start_act.append(["str", argv[1]])
            argv = argv[2:]
        elif argv[0] == "-sd": # open savex.dat file
            app.start_act.append(["savedat", argv[1]])
            argv = argv[2:]
        elif argv[0] == "-t": # open translation
            app.start_act.append(["tran", argv[1]])
            argv = argv[2:]
        else:
            app.start_act.append(["open", argv[0]])
            argv = argv[1:]
    app.mainloop()

    
if __name__ == "__main__":
    main()
