var devices = ['nokia','iphone','ipod','ipad','blackberry','x11','android','android 1.5'];
var markersArray = [];
var marker;
var map;

function initialize(pinPoints) {
  var myOptions = {
    center: new google.maps.LatLng(-22.934365, -43.329048),
    zoom: 11,
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

  google.maps.event.addListener(marker, 'click', function() {
    window.location=buildVideoUrl(item);
  });
    
  insertCaption(marker, label, item);
  markersArray.push(marker);
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
        url='/hls/'+cam_id+'/index.m3u8';
        break;
    case 4: // blackberry
        document.write("Blackberry is not supported");
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
      //document.write('User agent found: '+i);
      return i;
    }
  }
  return -1;
}

function htmlContent(label, cam_id){
    var time = Date.now();
    var base = 5 * 60 * 1000;  // 5 minutes cache
    time = base * Math.round(time / base);

    return '<img src="/thumb/' + cam_id + '.jpg?' + time + '" ' +
           'width="320" height="240" alt="Image not available"></img>'+
           '<br>Camera ' + cam_id + '<br />' + label + '<br />';
}

// insere a legenda das câmeras
function insertCaption(marker, label, cam_id) {
    var infowindow = null;

    google.maps.event.addListener(marker, 'mouseover', function() {
        infowindow = new google.maps.InfoWindow({
            content: htmlContent(label, cam_id)
        });
        infowindow.open(map, marker);
    });

    google.maps.event.addListener(marker, 'mouseout', function() {
        infowindow.close();
        infowindow = null;
    });
}

