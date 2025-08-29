
from __future__ import unicode_literals
import os
import xbmc
from xbmc import executebuiltin
from xbmcaddon import Addon
from xbmcgui import Dialog
import xbmcvfs
import urlquick
import requests
import gzip
import time
import base64
import json
import xmltodict
from concurrent.futures.thread import ThreadPoolExecutor
from uuid import uuid4
from codequick.storage import PersistentDict
from codequick import Script
from codequick.script import Settings
from codequick.utils import keyboard
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
from distutils.version import LooseVersion

from .constants import AID, ANM, DICTIONARY, GSET, SSET, FEATURED_SRC, LOTPSEND, LOTPVERIFY, LOTPREF, TSREFTOK, TVAPICDN, TVMEDIA, TVAPIMEDIA, HOME_GET, TAB_CAT_SEE_ALL, CH_METADATA, SEARCH_API, devicetype, oprsys, osver, usergroup, useragent, httpuseragent, vercode, PID, CHANNELS_SRC, GET_EPG, EPG_SRC, IMG, IMG_POSTER

uaheaders = {"user-agent": useragent}
getBool = Settings.get_boolean
dtformat = " on %a, %d %b %Y at %I:%M %p"
dtnow = datetime.now()
strdtnow = str(dtnow.strftime(dtformat))
secinday = 86400
sestime = 18 * secinday
toktime = secinday / 13
dm = "RMX1945"
appname = "RJIL_JioTV"
appkey = "NzNiMDhlYzQyNjJm"
runPg = "RunPlugin(plugin://" + AID + "/resources/lib/"
runPgMain = runPg + "main/"
runPgRefresh = runPg + "utils/refresh_"

def notif(msg):
    Script.notify(msg, ANM)

def isLoggedIn(func):
    @wraps(func)
    def login_wrapper(*args, **kwargs):
        with PersistentDict("localdb") as db:
            headers = db.get("headers")
            exp = db.get("exp", 0)
            tokexp = db.get("tokexp", 0)
        if headers and exp > time.time():
            SSET("isloggedin", "true")
            return func(*args, **kwargs)
        elif headers and tokexp < time.time():
            executebuiltin(runPgRefresh + "token/)")
            return False
        elif headers and exp < time.time():
            executebuiltin(runPgRefresh + "sso_token/)")
            return False
        else:
            SSET("isloggedin", "false")
            notif("Login please")
            executebuiltin(runPgMain + "login/)")
            return False
    return login_wrapper

def expcheckTime():
    if getBool("isloggedin"):
        with PersistentDict("localdb") as db:
            tokexp = db.get("tokexp", 0)
            exp = db.get("exp", 0)
        if tokexp < time.time():
            executebuiltin(runPgRefresh + "token/)")
        if exp < time.time():
            executebuiltin(runPgRefresh + "sso_token/)")
    return tokexp, exp

if getBool("isloggedin"):
    tokexp, exp = expcheckTime()        
    SSET("atokexp", "authToken expiry" + datetime.fromtimestamp(int(tokexp)).strftime(dtformat))
    SSET("stokexp", "ssoToken expiry" + datetime.fromtimestamp(int(exp)).strftime(dtformat))

def epgcheckEpoch():
    epgStartEpoch = None
    if getBool("genepg"):
        epgstartTime = GSET("genepgtime")
        epgstartHours = int(epgstartTime.split(":")[0])
        epgstartMins = int(epgstartTime.split(":")[1])
        epgYear = dtnow.year
        epgMonth = dtnow.month
        epgDay = dtnow.day        
        currepgDT = datetime(epgYear, epgMonth, epgDay, epgstartHours, epgstartMins)
        currepgstartEpoch = currepgDT.timestamp()
        fwdepgDT = currepgDT + timedelta(days=1)
        fwdepgEpoch = fwdepgDT.timestamp()
        epgStartEpoch = currepgstartEpoch
        if currepgstartEpoch < time.time():
            epgStartEpoch = fwdepgEpoch
    return epgStartEpoch

def getHeaders():
    with PersistentDict("localdb") as db:
        return db.get("headers", {})

def getChannelHeaders():
    headers = getHeaders()
    return {
        "ssoToken": headers["ssotoken"],
        "userid": headers["userid"],
        "uniqueid": headers["uniqueid"],
        "crmid": headers["crmid"],
        "user-agent": useragent,
        "usergroup": usergroup,
        "deviceId": headers["deviceid"],
        "devicetype": devicetype,
        "os": oprsys,
        "osversion": osver,
        "versioncode": vercode,
    }

ftsrHeaders = {"devicetype": devicetype,"os": oprsys, "user-agent": httpuseragent, "usergroup": usergroup, "versionCode": vercode}

def getCachedDictionary():
    with PersistentDict("localdict") as db:
        dictionary = db.get("dictionary", False)
        if not dictionary:
            try:
                r = urlquick.get(DICTIONARY, verify=False, headers=uaheaders).text.encode('utf8')[3:].decode('utf8')
                db["dictionary"] = json.loads(r)
            except:
                Script.notify("Connection error ", "Retry after sometime")
        return db.get("dictionary", False)
                
def getFeatured():
    resp = urlquick.get(FEATURED_SRC, verify=False, headers=ftsrHeaders, max_age=-1).json()
    return resp.get("featuredNewData", [])

def getTabData(tabid):
    ftsrHeaders.update({"Content-Type": "application/json", "Usertype": usergroup})
    resp = urlquick.get(HOME_GET.format(str(tabid)), verify=False, headers=ftsrHeaders, max_age=-1).json()
    return resp.get("featuredNewData", [])

def getCatData(cat_id):
    ftsrHeaders.update({"content-type": "application/json"})
    resp = urlquick.get(TAB_CAT_SEE_ALL.format(cat_id), verify=False, headers=ftsrHeaders, max_age=-1).json()
    return resp.get("data", [])

def getChData(srno):
    ftsrHeaders.update({"content-type": "application/json"})
    resp = urlquick.get(CH_METADATA.format(str(srno)), verify=False, headers=ftsrHeaders, max_age=-1).json()
    return resp.get("data", {})

def getSearchData(kbd=True):
    query = keyboard("Search Channels, Live, Catchup in " + ANM) if kbd else GSET("searchquery")
    if kbd:
        SSET("searchquery", query)
    if query in ["", " ", None]:
        notif("No input search words")
        return
    else:
        resp = urlquick.get(SEARCH_API.format(query), verify=False, headers=ftsrHeaders, max_age=-1)
        return resp.json().get("data", {})

def quality_to_enum(quality_str, arr_len):
    mapping = {
        'Best': arr_len-1,
        'High': max(arr_len-2, arr_len-3),
        'Medium+': max(arr_len-3, arr_len-4),
        'Medium': max(2, arr_len-3),
        'Low': min(2, arr_len-3),
        'Lower': 1,
        'Lowest': 0,
    }
    if quality_str in mapping:
        return min(mapping[quality_str], arr_len-1)
    return 0

def logstatus(io):
    Logio = "Logged " + io
    tf = "true" if io == "in" else "false"
    SSET("lstatus", Logio + strdtnow)
    SSET("isloggedin", tf)
    SSET("atokreftime", "authToken logged" + strdtnow)
    SSET("stokreftime", "ssoToken logged" + strdtnow)
    notif(Logio)

@Script.register
def refresh_token(plugin):
    headers = getHeaders()
    resp = urlquick.post(TSREFTOK, json={
        "appName": headers.get("appName",""),
        "deviceId": headers.get("deviceid",""),
        "refreshToken": headers.get("refreshtoken","")
    }, headers={                
        "accept-encoding": "gzip",
        "accesstoken": headers.get("authtoken",""),
        "connection": "close",                
        "Content-Type": "application/json; charset=utf-8",
        "host": TSREFTOK.split("/")[2], 
        "uniqueid": headers.get("uniqueid",""),
        "devicetype": devicetype,
        "os": oprsys,
        "user-agent": httpuseragent,
        "versioncode": vercode,
    }, max_age=-1, verify=False, raise_for_status=False).json()
    if resp.get("authToken", "") != "":
        with PersistentDict("localdb") as db:
            db["headers"]["authtoken"] = resp.get("authToken")
            db["tokexp"] = time.time() + toktime
            if getBool("genepg"):
                epgStartEpoch = epgcheckEpoch()
                if db.get("epgExp", 0) < epgStartEpoch or db.get("epgExp", 0) == 0:
                    executebuiltin(runPg + "utils/epg/)")
    SSET("atokreftime", "authToken refreshed" + strdtnow)
    return None

@Script.register
def refresh_sso_token(plugin):        
    headers = getHeaders()
    resp = urlquick.get(LOTPREF, headers={
                "Accept-Encoding": "gzip",
                "deviceid": headers.get("deviceid"),
                "devicetype": devicetype,
                "Host": TVMEDIA[8:-6],
                "os": oprsys,
                "ssoToken": headers.get("ssotoken"),
                "uniqueid": headers.get("uniqueid"),
                "User-Agent": httpuseragent,
                "versionCode": vercode,
            }, max_age=-1, verify=False, raise_for_status=False).json()
    if resp.get("ssoToken", "") != "":
        with PersistentDict("localdb") as db:
            db["headers"]["ssotoken"] = resp.get("ssoToken")
            db["exp"] = time.time() + sestime
    SSET("stokreftime", "ssoToken refreshed" + strdtnow)
    return None

def login(mobile, otp):
    resp = None
    mobile = "+91" + mobile
    otpbody = {
            "number": base64.b64encode(mobile.encode("ascii")).decode("ascii"),
            "otp": otp,
            "deviceInfo": {
                "consumptionDeviceName": dm,
                "info": {
                    "type": oprsys,
                    "platform": {
                        "name": dm
                    },
                    "androidId": str(uuid4()),
                }
            }
        }
    resp = urlquick.post(LOTPVERIFY, json=otpbody, headers={"User-Agent": httpuseragent, "devicetype": "phone", "os": "android", "appname": appname}, max_age=-1, verify=False, raise_for_status=False).json()
    if resp.get("ssoToken", "") != "":
        _CREDS = {
            "authtoken": resp.get("authToken"),
            "refreshtoken": resp.get("refreshToken"),
            "ssotoken": resp.get("ssoToken"),
            "deviceid": resp.get("deviceId"),
            "userid": resp.get("sessionAttributes", {}).get("user", {}).get("uid"),
            "uniqueid": resp.get("sessionAttributes", {}).get("user", {}).get("unique"),
            "crmid": resp.get("sessionAttributes", {}).get("user", {}).get("subscriberId"),
            "subscriberid": resp.get("sessionAttributes", {}).get("user", {}).get("subscriberId"),
        }
        headers = {
            "appName": appname,
            "devicetype": devicetype,
            "os": oprsys,
            "osversion": osver,
            "user-agent": useragent,
            "usergroup": usergroup,
            "versioncode": vercode,
            "dm": dm
        }
        headers.update(_CREDS)
        with PersistentDict("localdb") as db:
            db["headers"] = headers
            db["exp"] = time.time() + sestime
            db["tokexp"] = time.time() + toktime
            epgStartEpoch = epgcheckEpoch()
            db["epgExp"] = epgStartEpoch
        logstatus("in")
        return None
    else:
        msg = resp.get("message", ANM)
        SSET("isloggedin", "false")
        notif("Login Failed " + msg)
        return msg

def sendOTP(mobile):
    mobile = "+91" + mobile
    body = {
"number": base64.b64encode(mobile.encode("ascii")).decode("ascii")
    }
    sotpheaders = {
        "user-agent": httpuseragent, 
        "os": oprsys, 
        "host": TVAPIMEDIA[8:-1], 
        "devicetype": devicetype, 
        "appname": appname
    }
    resp = urlquick.post(LOTPSEND, json=body, headers=sotpheaders, max_age=-1, verify=False, raise_for_status=False)
    if resp.status_code != 204:
        return resp.json().get("errors", [{}])[-1].get("message")
    return None

def check_addon(addonid, minVersion=False):
    try:
        curVersion = Script.get_info("version", addonid)
        if minVersion and LooseVersion(curVersion) < LooseVersion(minVersion):
            Script.log('{addon} {curVersion} doesn\'t satisfy required version {minVersion}.'.format(
                addon=addonid, curVersion=curVersion, minVersion=minVersion))
            Dialog().ok("Error", "{minVersion} version of {addon} is required to play this content.".format(
                addon=addonid, minVersion=minVersion))
            return False
        return True
    except RuntimeError:
        Script.log('{addon} is not installed.'.format(addon=addonid))
        if not _install_addon(addonid):
            Dialog().ok("Error",
                        "[B]{addon}[/B] is missing on your Kodi install. This add-on is required to play this content.".format(addon=addonid))
            return False
        return True

def _install_addon(addonid):
    try:
        executebuiltin('InstallAddon({})'.format(addonid), wait=True)
        version = Script.get_info("version", addonid)
        Script.log(
            '{addon} {version} add-on installed from repo.'.format(addon=addonid, version=version))
        return True
    except RuntimeError:
        Script.log('{addon} add-on not installed.'.format(addon=addonid))
        return False

def cleanLocalCache():
    with PersistentDict("localdict") as db:
        del db["dictionary"]

def logout():
    with PersistentDict("localdb") as db:
        del db["headers"]
        del db["tokexp"]
        del db["exp"]
        del db["epgExp"]
    cleanLocalCache()
    logstatus("out")


_signals = defaultdict(list)
_skip = defaultdict(int)

def emit(signal, *args, **kwargs):
    if _skip[signal] > 0:
        _skip[signal] -= 1
        return

    for f in _signals.get(signal, []):
        f(*args, **kwargs)

class Monitor(xbmc.Monitor):
    def onSettingsChanged(self):
        emit('on_settings_changed')

monitor = Monitor()

def kodi_rpc(method, params=None, raise_on_error=False):
    try:
        payload = {'jsonrpc': '2.0', 'id': 1}
        payload.update({'method': method})
        if params:
            payload['params'] = params

        data = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
        if 'error' in data:
            raise Exception('Kodi RPC "{} {}" returned Error: "{}"'.format(
                method, params or '', data['error'].get('message')))

        return data['result']
    except Exception as e:
        if raise_on_error:
            raise
        else:
            return {}

def set_kodi_setting(key, value):
    return kodi_rpc('Settings.SetSettingValue', {'setting': key, 'value': value})

def same_file(path_a, path_b):
    if path_a.lower().strip() == path_b.lower().strip():
        return True

    stat_a = os.stat(path_a) if os.path.isfile(path_a) else None
    if not stat_a:
        return False

    stat_b = os.stat(path_b) if os.path.isfile(path_b) else None
    if not stat_b:
        return False

    return (stat_a.st_dev == stat_b.st_dev) and (stat_a.st_ino == stat_b.st_ino) and (stat_a.st_mtime == stat_b.st_mtime)


def safe_copy(src, dst, del_src=False):
    src = xbmcvfs.translatePath(src)
    dst = xbmcvfs.translatePath(dst)

    if not xbmcvfs.exists(src) or same_file(src, dst):
        return

    if xbmcvfs.exists(dst):
        if xbmcvfs.delete(dst):
            Script.log('Deleted: {}'.format(dst))
        else:
            Script.log('Failed to delete: {}'.format(dst))

    if xbmcvfs.copy(src, dst):
        Script.log('Copied: {} > {}'.format(src, dst))
    else:
        Script.log('Failed to copy: {} > {}'.format(src, dst))

    if del_src:
        xbmcvfs.delete(src)

def _setup(m3uPath, epgUrl):
    addon = Addon(PID)
    ADDON_NAME = addon.getAddonInfo('name')
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    instance_filepath = os.path.join(addon_path, 'instance-settings-91.xml')

    kodi_rpc('Addons.SetAddonEnabled', {
                'addonid': PID, 'enabled': False})

    if LooseVersion(addon.getAddonInfo('version')) >= LooseVersion('20.8.0'):
        xbmcvfs.delete(instance_filepath)

        for file in os.listdir(addon_path):
            if file.startswith('instance-settings-') and file.endswith('.xml'):
                file_path = os.path.join(addon_path, file)
                with open(file_path) as f:
                    data = f.read()

                if 'id="m3uPath">{}</setting>'.format(m3uPath) in data or 'id="epgUrl">{}</setting>'.format(epgUrl) in data:
                    xbmcvfs.delete(os.path.join(addon_path, file_path))
                else:
                    safe_copy(file_path, file_path+'.bu', del_src=True)
        
        kodi_rpc('Addons.SetAddonEnabled', {
                    'addonid': PID, 'enabled': True})

        while not os.path.exists(os.path.join(addon_path, 'instance-settings-1.xml')):
            monitor.waitForAbort(1)
        kodi_rpc('Addons.SetAddonEnabled', {
                    'addonid': PID, 'enabled': False})
        monitor.waitForAbort(1)

        safe_copy(os.path.join(addon_path, 'instance-settings-1.xml'),
                    instance_filepath, del_src=True)
        
        with open(instance_filepath, 'r') as f:
            data = f.read()
        with open(instance_filepath, 'w') as f:
            f.write(data.replace('Migrated Add-on Config', ANM))
        
        for file in os.listdir(addon_path):
            if file.endswith('.bu'):
                safe_copy(os.path.join(addon_path, file), os.path.join(
                    addon_path, file[:-3]), del_src=True)
        kodi_rpc('Addons.SetAddonEnabled', {
                    'addonid': PID, 'enabled': True})
        
    else:
        kodi_rpc('Addons.SetAddonEnabled', {
                    'addonid': PID, 'enabled': True})
        

    set_kodi_setting('epg.futuredaystodisplay', 1)
    #  set_kodi_setting('epg.ignoredbforclient', True)
    set_kodi_setting('pvrmanager.syncchannelgroups', True)
    set_kodi_setting('pvrmanager.preselectplayingchannel', True)
    set_kodi_setting('pvrmanager.backendchannelorder', True)
    set_kodi_setting('pvrmanager.usebackendchannelnumbers', True)
    
    notif("IPTV Setup Done, Restart KODI.")
    return True

channel = []
programme = []
error = []
result = []
done = 0

def genEPG(i, c):
    epglimpast = GSET("epglimpast")
    epglimfut = GSET("epglimfut")
    limpast = -abs(int(epglimpast) + 1)
    limfut = abs(int(epglimfut) + 2)
    global channel, programme, error, result, GET_EPG, CHANNELS_SRC, IMG, IMG_POSTER, done
    for day in range(limpast, limfut):
        try:
            resp = requests.get(
                GET_EPG,
                params={"offset": day, "channel_id": c["channel_id"], "langId": "6"},
                headers={"user-agent": httpuseragent},
                timeout=10,
            ).json()
            day == 0 and channel.append(
                {
                    "@id": c["channel_id"],
                    "display-name": c["channel_name"],
                    "icon": {"@src": f"{IMG}{c['logoUrl']}"},
                }
            )
            for eachEPG in resp.get("epg"):
                pdict = {
                    "@start": datetime.utcfromtimestamp(
                        int(eachEPG["startEpoch"] * 0.001)
                    ).strftime("%Y%m%d%H%M%S"),
                    "@stop": datetime.utcfromtimestamp(
                        int(eachEPG["endEpoch"] * 0.001)
                    ).strftime("%Y%m%d%H%M%S"),
                    "@channel": eachEPG["channel_id"],
                    "@catchup-id": eachEPG["srno"],
                    "title": eachEPG["showname"],
                    "desc": eachEPG["description"],
                    "category": eachEPG["showCategory"],
                    "icon": {"@src": f"{IMG_POSTER}{eachEPG['episodePoster']}"},
                }
                if eachEPG["episode_num"] > -1:
                    pdict["episode-num"] = {
                        "@system": "xmltv_ns",
                        "#text": f"0.{eachEPG['episode_num']}",
                    }
                if eachEPG.get("director") or eachEPG.get("starCast"):
                    pdict["credits"] = {
                        "director": eachEPG.get("director"),
                        "actor": eachEPG.get("starCast")
                        and eachEPG.get("starCast").split(", "),
                    }
                if eachEPG.get("episode_desc"):
                    pdict["sub-title"] = eachEPG.get("episode_desc")
                programme.append(pdict)
        except Exception as e:
            print(e)
            error.append(c["channel_id"])
    done += 1

@Script.register
def epg(plugin):
    notif("Generating EPG...")
    stime = time.time()
    raw = requests.get(
        CHANNELS_SRC,
        headers={"user-agent": httpuseragent},
        timeout=10,
    ).json()
    result = raw.get("result")
    with ThreadPoolExecutor() as e:
        e.map(genEPG, range(len(result)), result)
    epgdict = {"tv": {"channel": channel, "programme": programme}}
    epgxml = xmltodict.unparse(epgdict, pretty=True)
    with open(EPG_SRC, "wb+") as f:
        f.write(gzip.compress(epgxml.encode("utf-8")))
    print("EPG updated", datetime.now())
    if len(error) > 0:
        print(f"error in {error}")
    if getBool("genepg"):
        epgStartEpoch = epgcheckEpoch()
        with PersistentDict("localdb") as db:
            db["epgExp"] = epgStartEpoch
    notif(f"EPG took {time.time()-stime:.2f} seconds")
