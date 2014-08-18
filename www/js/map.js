var devices = ['nokia', 'iphone', 'ipod', 'ipad', 'blackberry',
               'x11', 'android', 'android 1.5'];
var markersArray = [];
var marker;
var map;

function initialize(pinPoints) {
    console.log('intialize map');
    var myOptions = {
        center: new google.maps.LatLng(-22.932933, -43.200397),
        zoom: 13,
        mapTypeId: google.maps.MapTypeId.ROADMAP
    };
    map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);
    var trafficLayer = new google.maps.TrafficLayer();
    trafficLayer.setMap(map);
    pinPoints(map);
}

//insere o maker e configura as funções do click
function insertPinPoint(myLatlng, item, map, label, icon){
    marker = new google.maps.Marker({
        position: myLatlng,
        map: map,
        flat: true,
        icon : icon
    });

    insertVideoWindow(marker, item);
    insertCaption(marker, label, item);
    markersArray.push(marker);
}

function insertVideoWindow(marker, item) {
    google.maps.event.addListener(marker, 'click', function() {
        $.fancybox.open({
            href: buildVideoUrl(item),
            padding: 0,
            autoScale: false,
            autoSize: false,
            autoDimensions: false,
            fitToView: false,
            transitionIn: 'none',
            transitionOut: 'none',
            title: this.title,
            width: 870,
            height: 496,
            type: 'iframe'
        });
    });
}

function buildVideoUrl(cam_id){
    var userAgent = navigator.userAgent.toLowerCase();
    var url = 'viewer.html?id=' + cam_id;

    switch(userAgentDetect(userAgent)){
    case 0: // Nokia
        document.write('Nokia without flash is not supported');
        break;
    case 1: // iphone, ipod ou ipad
    case 2:
    case 3:
    case 6: // Android
        url = '/hls/' + cam_id + '/index.m3u8';
        break;
    case 4: // Blackberry
        document.write('Blackberry is not supported');
        break;
    case 5: // Linux (flash)
        break;
    case 7: // Old Android (Flash not supported)
        document.write('Android 1.5 does not support flash');
        break;
    default:
        break;
    }

    return (url);
}

function userAgentDetect(userAg){ 
    for(var i = 0; i < devices.length; i++) {
        if (userAg.search(devices[i]) > 0) {
            console.log('User agent found: ' + i);
            return i;
        }
    }
    return -1;
}

function htmlContent(label, cam_id, cache){
    var time = Date.now();
    if (cache == undefined) {
        cache = 5 * 60 * 1000;  // 5 minutes cache
    }
    var img_error = "'img_error.png'";
    time = cache ? cache * Math.round(time / cache) : time;


    return '<img src="/thumb/' + cam_id + '.jpg?' + time + '" ' +
           'width="320"' +
           'onerror="this.src =' + img_error + '"></img>'+
           '<br>Camera ' + cam_id + '<br />' + label + '<br />';
}

// insere a legenda das câmeras
function insertCaption(marker, label, cam_id, cache) {
    var infowindow = null;

    google.maps.event.addListener(marker, 'mouseover', function() {
        infowindow = new google.maps.InfoWindow({
            content: htmlContent(label, cam_id, cache)
        });
        infowindow.open(map, marker);
    });

    google.maps.event.addListener(marker, 'mouseout', function() {
        infowindow.close();
        infowindow = null;
    });
}

function mobileStreamPinPoints() {
    var ws = new WebSocket('ws://' + location.host + '/mobile/location');
    var markers = []; // TODO Add here

    ws.onopen = function () {
        ws.send("Hello, world");
    };

    ws.onmessage = function (evt) {
        //console.log(evt.data);
        var data = JSON.parse(evt.data);
        if (data.request == 'all') {
            $(data.content).each(function (i, x) {
                try {
                    var pos = x.position.slice(-1)[0].coord;
                } catch(TypeError) {
                    return;
                }
                console.log(pos);
                marker = new google.maps.Marker({
                    position: new google.maps.LatLng(pos[0], pos[1]),
                    map: map,
                    flat: true,
                    icon: 'mobile.png'
                });
                var item = 'M_' + x._id.$oid;
                insertCaption(marker, '', item, 10 * 1000);
                insertVideoWindow(marker, item);
            });
        }
        else if (data.request == 'update'){

        }
    };
}
