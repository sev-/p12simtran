#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# romiq.kh@gmail.com, 2014

import sys, os
import tkinter
from tkinter import ttk, font
from idlelib.WidgetRedirector import WidgetRedirector

import petka

APPNAME = "P1&2 Explorer"

# thanx to http://effbot.org/zone/tkinter-text-hyperlink.htm
class HyperlinkManager:
    def __init__(self, text):
        self.text = text
        self.text.tag_config("hyper", foreground = "blue", underline = 1)
        self.text.tag_bind("hyper", "<Enter>", self._enter)
        self.text.tag_bind("hyper", "<Leave>", self._leave)
        self.text.tag_bind("hyper", "<Button-1>", self._click)
        self.reset()

    def reset(self):
    	self.links = {}

    def add(self, action):
        # add an action to the manager.  returns tags to use in
        # associated text widget
        tag = "hyper-{}".format(len(self.links))
        self.links[tag] = action
        return "hyper", tag

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
        self.sim = None
        # gui
        self.curr_main = 0 # 0 - frame, 1 - canvas
        self.curr_mode = 0
        self.curr_mode_sub = None
        self.curr_gui = []
        self.curr_lb_acts = None
        # canvas
        self.curr_width = 0
        self.curr_height = 0
        self.need_update = False
        self.canv_view_fact = 1
        self.main_image = tkinter.PhotoImage(width = 1, height = 1)
        self.after_idle(self.on_first_display)
        
    def create_widgets(self):
        
        ttk.Style().configure("Tool.TButton", width = -1) # minimal width
        ttk.Style().configure("TLabel", padding = self.pad)
        ttk.Style().configure('Info.TFrame', background = 'white', foreground = "black")
        
        # main paned
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
        
        self.update_after()
        self.update_gui()

    def create_menu(self):
        self.menubar = tkinter.Menu(self.master)
        self.master.configure(menu = self.menubar)

        self.menufile = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menufile,
                label = "File")
        self.menufile.add_command(
                command = self.on_open_data,
                label = "Open data...")
        self.menufile.add_separator()
        self.menufile.add_command(
                command = self.on_exit,
                label = "Quit")    

        self.menuedit = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menuedit,
                label = "Edit")
        self.menuedit.add_command(
                command = self.on_outline,
                label = "Outline")
        self.menuedit.add_separator()
        self.menuedit.add_command(
                command = self.on_list_parts,
                label = "Select part")
        self.menuedit.add_separator()
        self.menuedit.add_command(
                command = self.on_list_res,
                label = "Resources")
        self.menuedit.add_command(
                command = self.on_list_objs,
                label = "Objects")
        self.menuedit.add_command(
                command = self.on_list_scenes,
                label = "Scenes")
        self.menuedit.add_command(
                command = self.on_list_names,
                label = "Names")
        self.menuedit.add_command(
                command = self.on_list_invntr,
                label = "Invntr")

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
        #self.currMode += 1
        #if self.currMode > 1:
        #    self.currMode = 0
        self.update_after()
        
    def on_resize_view(self, event):
        self.update_after()

    def update_canvas(self):
        if self.curr_main == 0:          
            return
        # draw grahics
        c = self.canv_view
        c.delete(tkinter.ALL)
        if self.sim is None: return
        # Preview image        
        self.canv_image = self.main_image.copy()
        w = self.canv_view.winfo_width() 
        h = self.canv_view.winfo_height()
        if (w == 0) or (h == 0): 
            return
        
        scale = 0 #self.RadioGroupScale.get()
        if scale == 0: # Fit
            try:
                psc = w / h
                isc = self.curr_width / self.curr_height
                if psc < isc:
                    if w > self.curr_width:
                        fact = w // self.curr_width
                    else:
                        fact = -self.curr_width // w
                else:
                    if h > self.curr_height:
                        fact = h // self.curr_height
                    else:
                        fact = -self.curr_height // h
            except:
                fact = 1
        else:
            fact = scale

        # place on canvas
        if fact > 0:
            pw = self.curr_width * fact
            ph = self.curr_height * fact
        else:
            pw = self.curr_width // -fact
            ph = self.curr_height // -fact

        cw = max(pw, w)
        ch = max(ph, h)
        c.config(scrollregion = (0, 0, cw - 2, ch - 2))
    
        if fact > 0:
            self.canv_image = self.canv_image.zoom(fact)
        else:
            self.canv_image = self.canv_image.subsample(-fact)
        self.canv_image_fact = fact
        #print("Place c %d %d, p %d %d" % (cw, ch, w, h))
        c.create_image(cw // 2, ch // 2, image = self.canv_image)
       
    def make_image(self, width, height, data):
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

    def update_gui_add_left_listbox(self, text, acts = None):
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
        lb = tkinter.Listbox(frm_lb,
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

        self.curr_lb_acts = acts
        if acts:
            for name, cb in acts:
                lb.insert(tkinter.END, name)
        self.curr_lb = lb
        return lb
    
    def update_gui(self):
        self.canv_view.delete(tkinter.ALL)
        for item in self.curr_gui:
            item()
        self.curr_gui = []

        if self.curr_main == 0:
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
            self.text_view.grid_forget()
            self.canv_view.grid(row = 0, column = 0, \
                sticky = tkinter.N + tkinter.S + tkinter.E + tkinter.W)
            self.canv_view.configure(
                xscrollcommand = self.scr_view_x.set,
                yscrollcommand = self.scr_view_y.set
            )
            self.scr_view_x.config(command = self.canv_view.xview)
            self.scr_view_y.config(command = self.canv_view.yview)

        if self.curr_mode == 0:
            if self.sim is None:
                # open some data
                acts = [
                    ("Open data", self.on_open_data)
                ]
                self.update_gui_add_left_listbox("Outline", acts)                
            else:
                def tst_img():
                    self.curr_main = 1
                    self.main_image = tkinter.PhotoImage(\
                        file = "img/splash.gif")
                    self.curr_width = self.main_image.width()
                    self.curr_height = self.main_image.height()
                    self.update_gui()
                def tst_info():
                    self.change_gui(0, 99)
                acts = [
                    ("Parts", self.on_list_parts),
                    ("Resources ({})".format(len(self.sim.res)), \
                        self.on_list_res),
                    ("Objects ({})".format(len(self.sim.objects)), \
                        self.on_list_objs),
                    ("Scenes ({})".format(len(self.sim.scenes)), \
                        self.on_list_scenes),
                    ("Names ({})".format(len(self.sim.names)), \
                        self.on_list_names),
                    ("Invntr ({})".format(len(self.sim.invntr)), \
                        self.on_list_invntr),
                    ("-", None),
                    ("Test image", tst_img),
                    ("Test info", tst_info),
                ]
                self.update_gui_add_left_listbox("Outline: part {} chapter {}".\
                    format(self.sim.curr_part, self.sim.curr_chap), acts)                
        elif self.curr_mode == 99:
            acts = [
                ("<- outline", self.on_outline)
            ]
            self.update_gui_add_left_listbox("Test info", acts)                
        elif self.curr_mode == 90:
            # list parts
            lb = self.update_gui_add_left_listbox("Parts")
            for part in self.sim.parts:
                lb.insert(tkinter.END, part)
        elif self.curr_mode == 100:
            # list resources
            if self.curr_mode_sub is None:
                lb = self.update_gui_add_left_listbox("Resources") 
                for res_id in self.sim.resord:
                    lb.insert(tkinter.END, "{} - {}".format(res_id, \
                        self.sim.res[res_id]))
            else:
                lb = self.update_gui_add_left_listbox("Resources: {}".\
                    format(self.curr_mode_sub))
                for res_id in self.sim.resord:
                    if self.sim.res[res_id].upper().endswith\
                        ("." + self.curr_mode_sub):
                        lb.insert(tkinter.END, "{} - {}".format(res_id, \
                            self.sim.res[res_id]))
        elif self.curr_mode == 101:
            # list objects
            lb = self.update_gui_add_left_listbox("Objects")
            for obj in self.sim.objects:
                lb.insert(tkinter.END, "{} - {}".format(obj.idx, obj.name))
        elif self.curr_mode == 102:
            # list scenes
            lb = self.update_gui_add_left_listbox("Scenes")
            for scn in self.sim.scenes:
                lb.insert(tkinter.END, "{} - {}".format(scn.idx, scn.name))
        elif self.curr_mode == 103:
            # list names
            lb = self.update_gui_add_left_listbox("Names")
            for name in self.sim.namesord:
                lb.insert(tkinter.END, "{}".format(name))
        elif self.curr_mode == 104:
            # list invntr
            lb = self.update_gui_add_left_listbox("Invntr")
            for name in self.sim.invntrord:
                lb.insert(tkinter.END, "{}".format(name))
        self.update_info()
        self.update_after()

    def update_info(self):
        def stdinfo():
            self.text_view.delete(0.0, tkinter.END)
            self.text_view.insert(tkinter.INSERT, "<- Outline", \
                self.text_hl.add(self.on_outline))
            self.text_view.insert(tkinter.INSERT, "\n\n")

        self.text_hl.reset()
        if self.curr_mode == 0:
            self.text_view.delete(0.0, tkinter.END)
            if self.sim is None:
                self.text_view.insert(tkinter.INSERT, "No data loaded")
                self.text_view.insert(tkinter.INSERT, "Open data", \
                    self.text_hl.add(self.on_open_data))
            else:
                self.text_view.insert(tkinter.INSERT, \
                    "Select type from outline")
        elif self.curr_mode == 99:
            stdinfo()
            for i in range(100):
                self.text_view.insert(tkinter.INSERT, \
                    "Item {}\n".format(i))
        elif self.curr_mode == 90:
            stdinfo()
            self.text_view.insert(tkinter.INSERT, \
                "Current: part {} chapter {}\n\n  Resources: ".\
                    format(self.sim.curr_part, self.sim.curr_chap))
            self.text_view.insert(tkinter.INSERT, "{}".\
                format(len(self.sim.res)), \
                self.text_hl.add(self.on_list_res))
            self.text_view.insert(tkinter.INSERT, "\n  Objects:   ")
            self.text_view.insert(tkinter.INSERT, "{}".\
                format(len(self.sim.objects)), \
                self.text_hl.add(self.on_list_objs))
            self.text_view.insert(tkinter.INSERT, "\n  Scenes:    ")
            self.text_view.insert(tkinter.INSERT, "{}".\
                format(len(self.sim.scenes)), \
                self.text_hl.add(self.on_list_scenes))
            self.text_view.insert(tkinter.INSERT, "\n  Names:     ")
            self.text_view.insert(tkinter.INSERT, "{}".\
                format(len(self.sim.names)), \
                self.text_hl.add(self.on_list_names))
            self.text_view.insert(tkinter.INSERT, "\n  Invntr:    ")
            self.text_view.insert(tkinter.INSERT, "{}".\
                format(len(self.sim.invntr)), \
                self.text_hl.add(self.on_list_invntr))
        elif self.curr_mode == 100:
            stdinfo()
            self.text_view.insert(tkinter.INSERT, "Total: ")
            self.text_view.insert(tkinter.INSERT, "{}".\
                format(len(self.sim.res)), \
                self.text_hl.add(lambda: self.change_gui(0, 100)))
            self.text_view.insert(tkinter.INSERT, "\nFiletypes:\n")
            fts = {}
            for res in self.sim.res.values():
                fp = res.rfind(".")
                if fp >= 0:
                    ft = res[fp + 1:].upper()
                    fts[ft] = fts.get(ft, 0) + 1
            ftk = list(fts.keys())
            ftk.sort()
            for ft in ftk:
                self.text_view.insert(tkinter.INSERT, "  ")
                def make_cb(key):
                    def cb():
                        self.change_gui(0, 100, key)
                    return cb
                self.text_view.insert(tkinter.INSERT, ft, \
                    self.text_hl.add(make_cb(ft)))
                self.text_view.insert(tkinter.INSERT, ": {}\n".format(fts[ft]))
                
        elif self.curr_mode == 101:
            stdinfo()
        elif self.curr_mode == 102:
            stdinfo()
        else:
            stdinfo()
            
    def open_gui_elem(self, main, mode, idx):
        if self.curr_mode != mode:
            self.change_gui(main, mode)
        self.curr_lb.selection_set(idx)
        self.curr_lb.see(idx)
        self.on_left_listbox(None)
            
    def open_object(self, obj_id):
        for idx, obj in enumerate(self.sim.objects):
            if obj.idx == obj_id:
                self.open_gui_elem(0, 101, idx)
                break

    def open_scene(self, scn_id):
        for idx, obj in enumerate(self.sim.scenes):
            if obj.idx == scn_id:
                self.open_gui_elem(0, 102, idx)
                break

    def open_name(self, name_key):
        for idx, key in enumerate(self.sim.namesord):
            if key == name_key:
                self.open_gui_elem(0, 103, idx)
                break

    def open_invntr(self, inv_key):
        for idx, key in enumerate(self.sim.invntrord):
            if key == inv_key:
                self.open_gui_elem(0, 104, idx)
                break
                
    def change_gui(self, main, mode, sub = None):
        self.curr_main = main
        self.curr_mode = mode
        self.curr_mode_sub = sub
        self.update_gui()

    def on_left_listbox(self, event):
        def currsel():
            try:
                num = self.curr_lb.curselection()[0]
                num = int(num)
            except:
                pass
            return num

        def objinfo(tp, rec):
            self.text_view.insert(tkinter.INSERT, \
                ("Object" if tp else "Scene") + ":\n")
            self.text_view.insert(tkinter.INSERT, \
                "  Index:  {}\n  Name:   {}\n".format(rec.idx, rec.name))
            if rec.name in self.sim.names:
                self.text_view.insert(tkinter.INSERT, "  ")
                def make_cb(key):
                    def cb():
                        self.open_name(key)
                    return cb
                self.text_view.insert(tkinter.INSERT, "Alias", \
                    self.text_hl.add(make_cb(rec.name)))
                self.text_view.insert(tkinter.INSERT, \
                    ":  {}\n".format(self.sim.names[rec.name]))
            if rec.name in self.sim.invntr:
                self.text_view.insert(tkinter.INSERT, "  ")
                def make_cb(key):
                    def cb():
                        self.open_invntr(key)
                    return cb
                self.text_view.insert(tkinter.INSERT, "Invntr", \
                    self.text_hl.add(make_cb(rec.name)))
                self.text_view.insert(tkinter.INSERT, \
                    ": {}\n".format(self.sim.invntr[rec.name]))
        if self.curr_lb_acts:
            act = self.curr_lb_acts[currsel()]
            if act[1]:
                act[1]()
        elif self.curr_mode == 90:
            # parts
            try:
                part_id = self.curr_lb.curselection()[0]
                part_id = int(part_id)
            except:
                pass
            part_id = self.sim.parts[part_id]
            # parse
            pnum = part_id[5:]
            cnum = pnum.split("Chapter", 1)
            if len(cnum) > 1:
                pnum = int(cnum[0].strip(), 10)
                cnum = int(cnum[1].strip(), 10)
            else:
                cnum = 0
            self.sim.open_part(pnum, cnum)
            self.update_info()
            self.update_after()
        elif self.curr_mode == 100:
            # resources
            try:
                res_id = self.curr_lb.curselection()[0]
                res_id = self.curr_lb.get(res_id).split("-", 1)[0].strip()
                res_id = int(res_id)
            except:
                pass
            fn = self.sim.res[res_id]
            if fn[-4:].lower() == ".bmp":
                bmpdata = self.sim.fman.read_file(fn)
                bmp = petka.BMPLoader()
                bmp.load_data(bmpdata)
                self.main_image = \
                    self.make_image(bmp.width, bmp.height, bmp.rgb)
                self.curr_width = bmp.width
                self.curr_height = bmp.height
                self.curr_main = 1
                self.update_gui()
            print(fn)
        elif self.curr_mode == 101:
            # objects
            self.update_info()
            objinfo(True, self.sim.objects[currsel()])
        elif self.curr_mode == 102:
            # scenes
            self.update_info()
            objinfo(False, self.sim.scenes[currsel()])
        elif self.curr_mode == 103:
            # names
            self.update_info()
            key = self.sim.namesord[currsel()]
            self.text_view.insert(tkinter.INSERT, \
                "Alias: {}\n".format(key))
            self.text_view.insert(tkinter.INSERT, \
                "Value: {}\n\n".format(self.sim.names[key]))
            # search for objects
            self.text_view.insert(tkinter.INSERT, \
                "Applied for:")
            for obj in self.sim.objects:
                if obj.name == key:
                    self.text_view.insert(tkinter.INSERT, \
                        "\n  ")
                    def make_cb(idx):
                        def cb():
                            self.open_object(idx)
                        return cb
                    self.text_view.insert(tkinter.INSERT, \
                        "{} - {}".format(obj.idx, obj.name), \
                        self.text_hl.add(make_cb(obj.idx)))
        elif self.curr_mode == 104:
            # invntr
            self.update_info()
            key = self.sim.invntrord[currsel()]
            self.text_view.insert(tkinter.INSERT, \
                "Invntr: {}\n".format(key))
            self.text_view.insert(tkinter.INSERT, \
                "{}\n\n".format(self.sim.invntr[key]))
            # search for objects
            self.text_view.insert(tkinter.INSERT, \
                "Applied for:")
            for obj in self.sim.objects:
                if obj.name == key:
                    self.text_view.insert(tkinter.INSERT, \
                        "\n  ")
                    def make_cb(idx):
                        def cb():
                            self.open_object(idx)
                        return cb
                    self.text_view.insert(tkinter.INSERT, \
                        "{} - {}".format(obj.idx, obj.name), \
                        self.text_hl.add(make_cb(obj.idx)))

    def on_open_data(self):
        # open data - select TODO
        pass
        
    def on_outline(self):
        self.change_gui(0, 0)
        
    def on_list_parts(self):
        self.change_gui(0, 90)

    def on_list_res(self):
        self.change_gui(0, 100)

    def on_list_objs(self):
        self.change_gui(0, 101)

    def on_list_scenes(self):
        self.change_gui(0, 102)

    def on_list_names(self):
        self.change_gui(0, 103)

    def on_list_invntr(self):
        self.change_gui(0, 104)
        
    def open_data_from(self, folder):
        self.sim = petka.Engine()
        self.sim.load_data(folder, "cp1251")
        self.sim.open_part(0, 0)

def main():
    root = tkinter.Tk()
    app = App(master = root)
    if len(sys.argv) > 1:
        fn = sys.argv[1]
    else:
        fn = "."
    app.open_data_from(fn)
    app.mainloop()

    
if __name__ == "__main__":
    main()
