from machine import Pin, SPI

import time
import ustruct
import glcdfont
import framebuf
from micropython import const

_RDDSDR = const(0x0f) # Read Display Self-Diagnostic Result
_SLPOUT = const(0x11) # Sleep Out
_GAMSET = const(0x26) # Gamma Set
_DISPOFF = const(0x28) # Display Off
_DISPON = const(0x29) # Display On
_CASET = const(0x2a) # Column Address Set
_PASET = const(0x2b) # Page Address Set
_RAMWR = const(0x2c) # Memory Write
_RAMRD = const(0x2e) # Memory Read
_MADCTL = const(0x36) # Memory Access Control
_VSCRSADD = const(0x37) # Vertical Scrolling Start Address
_PIXSET = const(0x3a) # Pixel Format Set
_PWCTRLA = const(0xcb) # Power Control A
_PWCRTLB = const(0xcf) # Power Control B
_DTCTRLA = const(0xe8) # Driver Timing Control A
_DTCTRLB = const(0xea) # Driver Timing Control B
_PWRONCTRL = const(0xed) # Power on Sequence Control
_PRCTRL = const(0xf7) # Pump Ratio Control
_PWCTRL1 = const(0xc0) # Power Control 1
_PWCTRL2 = const(0xc1) # Power Control 2
_VMCTRL1 = const(0xc5) # VCOM Control 1
_VMCTRL2 = const(0xc7) # VCOM Control 2
_FRMCTR1 = const(0xb1) # Frame Rate Control 1
_DISCTRL = const(0xb6) # Display Function Control
_ENA3G = const(0xf2) # Enable 3G
_PGAMCTRL = const(0xe0) # Positive Gamma Control
_NGAMCTRL = const(0xe1) # Negative Gamma Control

_CHUNK = const(1024) #maximum number of pixels per spi write

def color565(r, g, b):
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3

class ILI9341:

    def __init__(self, spi, cs, dc, rst, w, h, r):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self._init_width = w
        self._init_height = h
        self.width = w
        self.height = h
        self.rotation = r
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=0)
        self.reset()
        self.init()
        self._scroll = 0
        self._buf = bytearray(_CHUNK * 2)
        self._colormap = bytearray(b'\x00\x00\xFF\xFF') #default white foregraound, black background
        self._x = 0
        self._y = 0
        self._font = glcdfont
        self.scrolling = False

    def set_color(self,fg,bg):
        self._colormap[0] = bg>>8
        self._colormap[1] = bg & 255
        self._colormap[2] = fg>>8
        self._colormap[3] = fg & 255

    def set_pos(self,x,y):
        self._x = x
        self._y = y

    def reset_scroll(self):
        self.scrolling = False
        self._scroll = 0
        self.scroll(0)

    def set_font(self, font):
        self._font = font

    def init(self):
        for command, data in (
            (_RDDSDR, b"\x03\x80\x02"),
            (_PWCRTLB, b"\x00\xc1\x30"),
            (_PWRONCTRL, b"\x64\x03\x12\x81"),
            (_DTCTRLA, b"\x85\x00\x78"),
            (_PWCTRLA, b"\x39\x2c\x00\x34\x02"),
            (_PRCTRL, b"\x20"),
            (_DTCTRLB, b"\x00\x00"),
            (_PWCTRL1, b"\x23"),
            (_PWCTRL2, b"\x10"),
            (_VMCTRL1, b"\x3e\x28"),
            (_VMCTRL2, b"\x86")):
            self._write(command, data)

        if self.rotation == 0:                  # 0 deg
            self._write(_MADCTL, b"\x48")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 1:                # 90 deg
            self._write(_MADCTL, b"\x28")
            self.width = self._init_width
            self.height = self._init_height
        elif self.rotation == 2:                # 180 deg
            self._write(_MADCTL, b"\x88")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 3:                # 270 deg
            self._write(_MADCTL, b"\xE8")
            self.width = self._init_width
            self.height = self._init_height
        elif self.rotation == 4:                # Mirrored + 0 deg
            self._write(_MADCTL, b"\xC8")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 5:                # Mirrored + 90 deg
            self._write(_MADCTL, b"\x68")
            self.width = self._init_width
            self.height = self._init_height
        elif self.rotation == 6:                # Mirrored + 180 deg
            self._write(_MADCTL, b"\x08")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 7:                # Mirrored + 270 deg
            self._write(_MADCTL, b"\xA8")
            self.width = self._init_width
            self.height = self._init_height
        else:
            self._write(_MADCTL, b"\x08")

        for command, data in (
            (_PIXSET, b"\x55"),
            (_FRMCTR1, b"\x00\x18"),
            (_DISCTRL, b"\x08\x82\x27"),
            (_ENA3G, b"\x00"),
            (_GAMSET, b"\x01"),
            (_PGAMCTRL, b"\x0f\x31\x2b\x0c\x0e\x08\x4e\xf1\x37\x07\x10\x03\x0e\x09\x00"),
            (_NGAMCTRL, b"\x00\x0e\x14\x03\x11\x07\x31\xc1\x48\x08\x0f\x0c\x31\x36\x0f")):
            self._write(command, data)
        self._write(_SLPOUT)
        time.sleep_ms(120)
        self._write(_DISPON)

    def reset(self):
        self.rst(0)
        time.sleep_ms(50)
        self.rst(1)
        time.sleep_ms(50)

    def _write(self, command, data=None):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([command]))
        self.cs(1)
        if data is not None:
            self._data(data)

    def _data(self, data):
        self.dc(1)
        self.cs(0)
        self.spi.write(data)
        self.cs(1)

    def _writeblock(self, x0, y0, x1, y1, data=None):
        self._write(_CASET, ustruct.pack(">HH", x0, x1))
        self._write(_PASET, ustruct.pack(">HH", y0, y1))
        self._write(_RAMWR, data)

    def _readblock(self, x0, y0, x1, y1, data=None):
        self._write(_CASET, ustruct.pack(">HH", x0, x1))
        self._write(_PASET, ustruct.pack(">HH", y0, y1))
        if data is None:
            return self._read(_RAMRD, (x1 - x0 + 1) * (y1 - y0 + 1) * 3)

    def _read(self, command, count):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([command]))
        data = self.spi.read(count)
        self.cs(1)
        return data

    def pixel(self, x, y, color=None):
        if color is None:
            r, b, g = self._readblock(x, y, x, y)
            return color565(r, g, b)
        if not 0 <= x < self.width or not 0 <= y < self.height:
            return
        self._writeblock(x, y, x, y, ustruct.pack(">H", color))

    def fill_rectangle(self, x, y, w, h, color=None):
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        w = min(self.width - x, max(1, w))
        h = min(self.height - y, max(1, h))
        if color:
            color = ustruct.pack(">H", color)
        else:
            color = self._colormap[0:2] #background
        for i in range(_CHUNK):
            self._buf[2*i]=color[0]; self._buf[2*i+1]=color[1]
        chunks, rest = divmod(w * h, _CHUNK)
        self._writeblock(x, y, x + w - 1, y + h - 1, None)
        if chunks:
            for count in range(chunks):
                self._data(self._buf)
        if rest != 0:
            mv = memoryview(self._buf)
            self._data(mv[:rest*2])

    def erase(self):
        self.fill_rectangle(0, 0, self.width, self.height)

    def blit(self, bitbuff, x, y, w, h):
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        w = min(self.width - x, max(1, w))
        h = min(self.height - y, max(1, h))
        chunks, rest = divmod(w * h, _CHUNK)
        self._writeblock(x, y, x + w - 1, y + h - 1, None)
        written = 0
        for iy in range(h):
            for ix in range(w):
                index = ix+iy*w - written
                if index >=_CHUNK:
                    self._data(self._buf)
                    written += _CHUNK
                    index   -= _CHUNK
                c = bitbuff.pixel(ix,iy)
                self._buf[index*2] = self._colormap[c*2]
                self._buf[index*2+1] = self._colormap[c*2+1]
        rest = w*h - written
        if rest != 0:
            mv = memoryview(self._buf)
            self._data(mv[:rest*2])

    def chars(self, str, x, y):
        str_w  = self._font.get_width(str)
        div, rem = divmod(self._font.height(),8)
        nbytes = div+1 if rem else div
        buf = bytearray(str_w * nbytes)
        pos = 0
        for ch in str:
            glyph, char_w = self._font.get_ch(ch)
            for row in range(nbytes):
                index = row*str_w + pos
                for i in range(char_w):
                    buf[index+i] = glyph[nbytes*i+row]
            pos += char_w
        fb = framebuf.FrameBuffer(buf,str_w, self._font.height(), framebuf.MONO_VLSB)
        self.blit(fb,x,y,str_w,self._font.height())
        return x+str_w

    def scroll(self, dy):
        self._scroll = (self._scroll + dy) % self.height
        self._write(_VSCRSADD, ustruct.pack(">H", self._scroll))

    def next_line(self, cury, char_h):
        global scrolling
        if not self.scrolling:
            res = cury + char_h
            self.scrolling = (res >= self.height)
        if self.scrolling:
            self.scroll(char_h)
            res = (self.height - char_h + self._scroll)%self.height
            self.fill_rectangle(0, res, self.width, self._font.height())
        return res

    def write(self, text): #does character wrap, compatible with stream output
        curx = self._x; cury = self._y
        char_h = self._font.height()
        width = 0
        written = 0
        for pos, ch in enumerate(text):
            if ch == '\n':
                if pos>0:
                    self.chars(text[written:pos],curx,cury)
                curx = 0; written = pos+1; width = 0
                cury = self.next_line(cury,char_h)
            else:
                char_w = self._font.get_width(ch)
                if curx + width + char_w >= self.width:
                    self.chars(text[written:pos], curx,cury)
                    curx = 0 ; written = pos; width = char_h
                    cury = self.next_line(cury,char_h)
                else:
                    width += char_w
        if written<len(text):
            curx = self.chars(text[written:], curx,cury)
        self._x = curx; self._y = cury


    def print(self, text): #does word wrap, leaves self._x unchanged
        cury = self._y; curx = self._x
        char_h = self._font.height()
        char_w = self._font.max_width()
        lines = text.split('\n')
        for line in lines:
            words = line.split(' ')
            for word in words:
                if curx + self._font.get_width(word) >= self.width:
                    curx = self._x; cury = self.next_line(cury,char_h)
                    while self._font.get_width(word) > self.width:
                        self.chars(word[:self.width//char_w],curx,cury)
                        word = word[self.width//char_w:]
                        cury = self.next_line(cury,char_h)
                if len(word)>0:
                    curx = self.chars(word+' ', curx,cury)
            curx = self._x; cury = self.next_line(cury,char_h)
        self._y = cury

import tt14

RED = const(0XF800)  # (255, 0, 0)
GREEN = const(0X07E0)  # (0, 255, 0)
BLUE = const(0X001F)  # (0, 0, 255)
YELLOW = const(0XFFE0)  # (255, 255, 0)
FUCHSIA = const(0XF81F)  # (255, 0, 255)
AQUA = const(0X07FF)  # (0, 255, 255)
MAROON = const(0X8000)  # (128, 0, 0)
DARKGREEN = const(0X0400)  # (0, 128, 0)
NAVY = const(0X0010)  # (0, 0, 128)
TEAL = const(0X0410)  # (0, 128, 128)
PURPLE = const(0X8010)  # (128, 0, 128)
OLIVE = const(0X8400)  # (128, 128, 0)
ORANGE = const(0XFC00)  # (255, 128, 0)
DEEP_PINK = const(0XF810)  # (255, 0, 128)
CHARTREUSE = const(0X87E0)  # (128, 255, 0)
SPRING_GREEN = const(0X07F0)  # (0, 255, 128)
INDIGO = const(0X801F)  # (128, 0, 255)
DODGER_BLUE = const(0X041F)  # (0, 128, 255)
CYAN = const(0X87FF)  # (128, 255, 255)
PINK = const(0XFC1F)  # (255, 128, 255)
LIGHT_YELLOW = const(0XFFF0)  # (255, 255, 128)
LIGHT_CORAL = const(0XFC10)  # (255, 128, 128)
LIGHT_GREEN = const(0X87F0)  # (128, 255, 128)
LIGHT_SLATE_BLUE = const(0X841F)  # (128, 128, 255)
WHITE = const(0XFFFF)  # (255, 255, 255)
BLACK = const(0)

text = 'Fine'
spi = SPI(0, baudrate=32000000, sck=Pin(2), mosi=Pin(3), miso=Pin(4),) #SPI(2, baudrate=20000000, miso=Pin(19),mosi=Pin(23), sck=Pin(18))
display = ILI9341(spi, cs=Pin(5), dc=Pin(7), rst=Pin(6), w=320, h=240, r=3)
display.erase()
display.set_color(RED,0)
display.set_font(tt14)
display.set_pos(0,0)
display.print(text)
display.set_pos(0,20)
display.print(text)
display.set_pos(40,20)
display.print(text)
for x in range(0,100):
    display.pixel(2*x,x,BLUE)
