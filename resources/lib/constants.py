import xbmcaddon
import os
from xbmcaddon import Addon
from xbmcvfs import translatePath

# Add-on Information
ADD = xbmcaddon.Addon()
AIN = ADD.getAddonInfo
AID = AIN("id")  # Add-on ID
ANM = AIN("name")  # Add-on Name
PRO = AIN("profile")  # Add-on Profile Path
PTH = AIN("path")  # Add-on Installation Path
ICO = AIN("icon")  # Add-on Icon Path
FNR = AIN("fanart")  # Add-on Fanart Path

# Settings Access
GSET = ADD.getSetting
SSET = ADD.setSetting
PATH_PRO = os.path.join(translatePath(PRO))  # Translated Profile Path

# Add-on Dependencies
PID = "pvr.iptvsimple"  # PVR IPTV Simple Client
IID = "inputstream.adaptive"  # InputStream Adaptive

# Device and User Information
devicetype = GSET("devicetype").lower()
oprsys = GSET("oprsys").lower()
osver = GSET("osver")
usergroup = GSET("usergroup")
useragent = GSET("useragent")
httpuseragent = GSET("httpuseragent")
vercode = GSET("vercode")
langId = "&langId=6"

# Filters and Tabs
filterBy = ["Languages", "Categories"]
tabsDict = {
    1: "For You",
    3: "Shows",
    12: "Movies",
    13: "Specials",
    5: "News",
    4: "Sports",
    6: "Kids",
}

# API Endpoints
TVAPICDN = "https://jiotvapi.cdn.jio.com/apis/"
TVMEDIA = "https://tv.media.jio.com/apis/"
TVAPIMEDIA = "https://jiotvapi.media.jio.com/"

DICTIONARY = f"{TVAPICDN}v1.3/dictionary/dictionary?langId=6"

CHAPI = (
    f"{TVAPICDN}{GSET('chapiv')}/getMobileChannelList/get/"
    f"?devicetype={devicetype}&os={oprsys}&usertype={usergroup}&version={vercode}"
)
SSET("channelssource", CHAPI)
CHANNELS_SRC = GSET("channelssource")

PBV1URL = f"{TVAPIMEDIA}playback/apis/v1/geturl?{langId[1:]}"
PBV2URL = f"{TVMEDIA}{GSET('pbapiv')}/getchannelurl/getchannelurl?userLanguages=All{langId}"
PBAPI = PBV1URL if GSET("pbapiv") == "v1" else PBV2URL
SSET("channelurl", PBAPI)
GET_CHANNEL_URL = GSET("channelurl")

# EPG and Catch-Up
PAST_PROGS_EPISODES = f"{TVAPICDN}v1.3/allpastprogs/{{0}}?{langId[1:]}"
GET_EPG = f"{TVAPICDN}v1.3/getepg/get"
CATCHUP_SRC = f"{GET_EPG}?offset={{0}}&channel_id={{1}}{langId}"

# Featured Content
FEATURED_SRC = f"{TVMEDIA}v1.6/getdata/featurednew?start=0&limit=30{langId}"
CAROUSEL = f"{TVMEDIA}v2.2/carousel/get?tabid={{0}}"
HOME_GET = f"{TVMEDIA}v3.6/home/get?tabid={{0}}&userLanguages=1&page=0"
TAB_CAT_SEE_ALL = f"{TVMEDIA}v2.0/tab/categoryseeall?cat_id={{0}}"
CH_METADATA = f"{TVMEDIA}v1.3/metadata/get?srno={{0}}{langId}"
SEARCH_API = f"{TVMEDIA}v2.2/search/search?query={{0}}&mode=RECENTS{langId}"

# Login and Token Services
USLOTP = f"{TVAPIMEDIA}userservice/apis/v1/loginotp/"
LOTPSEND = f"{USLOTP}send"
LOTPVERIFY = f"{USLOTP}verify"
LOTPREF = f"{TVMEDIA}v2.0/loginotp/refresh?langId=6"
TSREFTOK = "https://auth.media.jio.com/tokenservice/apis/v1/refreshtoken?langId=6"

# Image URLs
IMG = "https://jiotvimages.cdn.jio.com/dare_images/images/"
IMG_POSTER = "https://jiotv.catchup.cdn.jio.com/dare_images/shows/"

# Local Paths
EPG_SRC = os.path.join(PATH_PRO, "jiotvepg.xml.gz")
EPG_URL = GSET("epg_url")
M3U_SRC = os.path.join(PATH_PRO, "jiotvplaylist.m3u")