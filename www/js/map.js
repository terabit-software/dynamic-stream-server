var devices = ['nokia', 'iphone', 'ipod', 'ipad', 'blackberry',
               'x11', 'android', 'android 1.5'];
var markersArray = [];
var marker;
var map;
var image_path = '/images/';

function initialize(pinPoints, myOptions, addTrafficLayer) {
    console.log('intialize map');
    map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);
    if(addTrafficLayer){
        var trafficLayer = new google.maps.TrafficLayer();
        trafficLayer.setMap(map);
    }
    pinPoints(map);
}

//insere o maker e configura as funções do click
function insertPinPoint(myLatlng, item, map, label, status){
    var marker = new google.maps.Marker({
        position: myLatlng,
        map: map,
        flat: true,
        icon : image_path + (status ? 'on.png' : 'off.png')
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
    var url = '/static/viewer.html?id=' + cam_id;

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
    var img_error = "'" + image_path +  "img_error.png'";
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

function setMobilePinPoint(name, pos){
    marker = new google.maps.Marker({
        position: new google.maps.LatLng(pos[0], pos[1]),
        map: map,
        flat: true,
        icon: image_path + 'mobile.png'
    });
    insertCaption(marker, '', name, 10 * 1000);
    insertVideoWindow(marker, name);
    return marker
}


function mobileStreamPinPoints() {
    var ws = new WebSocket('ws://' + location.host + '/mobile/location');
    var markers = {};

    ws.onopen = function () {
        ws.send("Hello, world");
    };

    ws.onmessage = function (evt) {
        console.log('>>> message received')
        //console.log(evt.data);
        var data = JSON.parse(evt.data);
        if (data.request == 'all') {
            $(data.content).each(function (i, x) {
                console.log(x.name);
                try {
                    var pos = x.position.coord;
                } catch(TypeError) {
                    return;
                }
                console.log(pos);
                markers[x.name] = setMobilePinPoint(x.name, pos);
            });
        }
        else if (data.request == 'update'){
            console.log(data.content);
            var name = data.content.name;
            try{
                markers[name].setMap(null);
            } catch (ReferenceError) {}

            if (data.content.info == 'finished'){
                return;
            }

            var pos = data.content.info.coord;
            markers[name] = setMobilePinPoint(name, pos);
        }
        else if (data.request == 'close') {
            try{
                markers[data.content.name].setMap(null);
            } catch (ReferenceError) {}
        }
    };
}
