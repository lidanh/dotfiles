"""Built-in MacBook More Space scaling through public CoreGraphics APIs.

No extra package, sudo, display-ID persistence, or external-display configuration.
Known Retina panel presets are checked against the actual available HiDPI modes.
"""
from contextlib import contextmanager
import ctypes as C

NATIVE=0x02000000  # kDisplayModeNativeFlag, IOKit/graphics/IOGraphicsTypes.h
MORE_SPACE={(2560,1600):(1680,1050), (3024,1964):(1800,1169), (3456,2234):(2056,1329)}

def size(mode):return mode['width'],mode['height']
def retina(mode):return mode['pixel_width']==2*mode['width'] and mode['pixel_height']==2*mode['height']

def select_mode(modes,current):
    panels={(m['pixel_width'],m['pixel_height']) for m in modes if m['flags'] & NATIVE}
    if len(panels)!=1 or next(iter(panels)) not in MORE_SPACE:
        raise ValueError(f'Cannot identify a supported built-in Retina panel: {sorted(panels)}; no display changes made')
    target=MORE_SPACE[next(iter(panels))]
    candidates=[m for m in modes if size(m)==target and retina(m) and m['gui']]
    if not candidates:raise ValueError(f'More Space {target[0]}x{target[1]} HiDPI is unavailable; no display changes made')
    # Zero denotes a dynamic/unspecified refresh rate (including ProMotion).
    # Prefer retaining it when that is what the current mode reports.
    return min(candidates,key=lambda m:(abs(m['hz']-current['hz']),-m['hz']))

class CoreGraphics:
    def __init__(self):
        self.cg=C.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        self.cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        p=C.c_void_p;u=C.c_uint32;i=C.c_int
        def bind(lib,name,args,result):
            f=getattr(lib,name);f.argtypes=args;f.restype=result
        bind(self.cg,'CGGetOnlineDisplayList',[u,C.POINTER(u),C.POINTER(u)],i)
        for name in ['CGDisplayIsBuiltin','CGDisplayIsActive','CGDisplayIsInMirrorSet']:bind(self.cg,name,[u],u)
        bind(self.cg,'CGDisplayCopyAllDisplayModes',[u,p],p)
        bind(self.cg,'CGDisplayCopyDisplayMode',[u],p)
        for name in ['Width','Height','PixelWidth','PixelHeight']:bind(self.cg,'CGDisplayModeGet'+name,[p],C.c_size_t)
        bind(self.cg,'CGDisplayModeGetIOFlags',[p],u)
        bind(self.cg,'CGDisplayModeGetRefreshRate',[p],C.c_double)
        bind(self.cg,'CGDisplayModeIsUsableForDesktopGUI',[p],C.c_bool)
        bind(self.cf,'CFArrayGetCount',[p],C.c_long)
        bind(self.cf,'CFArrayGetValueAtIndex',[p,C.c_long],p)
        bind(self.cf,'CFRelease',[p],None)
        bind(self.cf,'CFDictionaryCreate',[p,C.POINTER(p),C.POINTER(p),C.c_long,p,p],p)
        self.mode_key=p.in_dll(self.cg,'kCGDisplayShowDuplicateLowResolutionModes').value
        self.boolean_true=p.in_dll(self.cf,'kCFBooleanTrue').value
        bind(self.cg,'CGBeginDisplayConfiguration',[C.POINTER(p)],i)
        bind(self.cg,'CGConfigureDisplayWithDisplayMode',[p,u,p,p],i)
        bind(self.cg,'CGCompleteDisplayConfiguration',[p,u],i)
        bind(self.cg,'CGCancelDisplayConfiguration',[p],i)

    def displays(self):
        count=C.c_uint32();ids=(C.c_uint32*32)()
        error=self.cg.CGGetOnlineDisplayList(32,ids,C.byref(count))
        if error:raise ValueError(f'Cannot enumerate displays: CoreGraphics error {error}')
        return list(ids[:count.value])

    def builtin(self,d):return bool(self.cg.CGDisplayIsBuiltin(d))
    def active(self,d):return bool(self.cg.CGDisplayIsActive(d))
    def mirrored(self,d):return bool(self.cg.CGDisplayIsInMirrorSet(d))

    def read_mode(self,ref):
        if not ref:raise ValueError('Cannot read display mode; run in an active graphical login')
        return dict(ref=ref,width=self.cg.CGDisplayModeGetWidth(ref),height=self.cg.CGDisplayModeGetHeight(ref),
                    pixel_width=self.cg.CGDisplayModeGetPixelWidth(ref),pixel_height=self.cg.CGDisplayModeGetPixelHeight(ref),
                    flags=self.cg.CGDisplayModeGetIOFlags(ref),hz=self.cg.CGDisplayModeGetRefreshRate(ref),
                    gui=bool(self.cg.CGDisplayModeIsUsableForDesktopGUI(ref)))

    def current(self,d):
        ref=self.cg.CGDisplayCopyDisplayMode(d)
        try:return self.read_mode(ref)
        finally:
            if ref:self.cf.CFRelease(ref)

    @contextmanager
    def modes(self,d):
        # NULL options can omit HiDPI modes despite the API's 'All' name.
        keys=(C.c_void_p*1)(self.mode_key);values=(C.c_void_p*1)(self.boolean_true)
        options=self.cf.CFDictionaryCreate(None,keys,values,1,None,None)
        if not options:raise ValueError('Cannot create full display-mode options')
        try:array=self.cg.CGDisplayCopyAllDisplayModes(d,options)
        finally:self.cf.CFRelease(options)
        if not array:raise ValueError('Cannot enumerate built-in display modes')
        try:yield [self.read_mode(self.cf.CFArrayGetValueAtIndex(array,i)) for i in range(self.cf.CFArrayGetCount(array))]
        finally:self.cf.CFRelease(array)

    def apply(self,d,mode):
        config=C.c_void_p()
        error=self.cg.CGBeginDisplayConfiguration(C.byref(config))
        if error:raise ValueError(f'Cannot begin display configuration: {error}')
        error=self.cg.CGConfigureDisplayWithDisplayMode(config,d,mode['ref'],None)
        if error:
            self.cg.CGCancelDisplayConfiguration(config)
            raise ValueError(f'Cannot configure More Space: {error}')
        error=self.cg.CGCompleteDisplayConfiguration(config,2)  # kCGConfigurePermanently
        if error:raise ValueError(f'Cannot save More Space configuration: {error}')

def configure(*,dry=False,check_only=False,api=None,verbose=False):
    api=api or CoreGraphics();difference=False;found=False
    for display in api.displays():
        if not api.builtin(display):continue
        found=True
        if not api.active(display) or api.mirrored(display):
            print('DEFERRED: built-in More Space; open the lid and disable display mirroring, then run dots apply.')
            difference=True;continue
        with api.modes(display) as modes:
            current=api.current(display)
            if verbose:
                print('Built-in display current:',{k:v for k,v in current.items() if k!='ref'})
                print('Built-in display available modes:')
                for mode in modes:print({k:v for k,v in mode.items() if k!='ref'})
            target=select_mode(modes,current)
            if size(current)==size(target) and retina(current):continue
            difference=True
            print(f'DIFF: built-in display → More Space {target["width"]}x{target["height"]} HiDPI')
            if not dry and not check_only:
                api.apply(display,target)
                actual=api.current(display)
                if size(actual)!=size(target) or not retina(actual):raise ValueError('More Space change did not take effect; run dots check')
    if not found:
        print('DEFERRED: no online built-in display; run dots apply with the lid open in a graphical login.')
        difference=True
    return difference
