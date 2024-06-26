import { generateVertices } from './generateVerticesRadarDemo.js';

var scan = 0;
var time = 0;
var start = true;
var changingContent = false;

var settings = {};
settings["rlat"] = 35.33335;
settings["rlon"] = -97.27776;
settings["scanangle"] = 0.5;
settings["gateres"] = 250;

//set up mapbox map
mapboxgl.accessToken = 
"pk.eyJ1IjoicXVhZHdlYXRoZXIiLCJhIjoiY2pzZTI0cXFjMDEyMTQzbnQ2MXYxMzd2YSJ9.kHgQu2YL36SZUgpXMlfaFg";

var map = window.map = new mapboxgl.Map({
container:'map',
attributionControl:false,
zoom:3,
maxZoom:25,
minZoom:3,
//overlaying custom made mapboxGL map
//    style: 'mapbox://styles/quadweather/cjsgo4h6905rg1fmcimx6j9dr'
style: 'mapbox://styles/quadweather/ckftuk99o0lar1at0siprao95',
antialias:false,
keyboard:false,
zoom:10,
center:[settings.rlon, settings.rlat],
//pitch:70.,
//bearing:315
});
map.addControl(new mapboxgl.AttributionControl(),'top-right');
map.addControl(new mapboxgl.NavigationControl(),'top-left');

new mapboxgl.Marker()
.setLngLat([settings.rlon, settings.rlat])
.addTo(map)

new mapboxgl.Marker()
.setLngLat([-97.27775, 35.33305])
.addTo(map)


function createTexture(gl) {
  var colors = {"refc0":[
    '#00000000',
    '#00000000',
    '#744eadff',
    '#938d75ff',
    '#969153ff',
    '#d2d4b4ff',
    '#cccfb4ff',
    '#415b9eff',
    '#4361a2ff',
    '#6ad0e4ff',
    '#6fd6e8ff',
    '#35d55bff',
    '#11d518ff',
    '#095e09ff',
    '#1d6809ff',
    '#ead204ff',
    '#ffe200ff',
    '#ff8000ff',
    '#ff0000ff',
    '#710000ff',
    '#ffffffff',
    '#ff92ffff',
    '#ff75ffff',
    '#e10be3ff',
    '#b200ffff',
    '#6300d6ff',
    '#05ecf0ff',
    '#012020ff'
  ]}
  var values = {"refc0":[0,2,2, 28, 28, 51, 51, 96, 96, 114, 114, 124, 124, 153, 153, 164, 164, 187, 187, 210, 210, 221, 221, 232, 232, 244, 244, 255]};
  var colors = colors["refc0"];
  var levs = values["refc0"];
  var colortcanvas = document.getElementById("texturecolorbar");
  colortcanvas.width = 1200;
  colortcanvas.height = 1;
  var ctxt = colortcanvas.getContext('2d');
  ctxt.clearRect(0,0,colortcanvas.width,colortcanvas.height); 
  var grdt = ctxt.createLinearGradient(0,0,1200,0);
  var cmax = 255;
  var cmin = 0;
  var clen = colors.length;

  for (var i=0; i<clen; ++i) {
    console.log(i, (levs[i]-cmin)/(cmax-cmin));
    grdt.addColorStop((levs[i]-cmin)/(cmax-cmin),colors[i]);
  }
  ctxt.fillStyle = grdt;
  ctxt.fillRect(0,0,1200,1);
  var imagedata = ctxt.getImageData(0,0,1200,1);
  pageState.imagedata = imagedata;
  var imagetexture = gl.createTexture();
  
  gl.activeTexture(gl.TEXTURE1); // Using gl.TEXTURE0 leads to the need of rebinding the texture on every call of layer.render
  gl.bindTexture(gl.TEXTURE_2D, imagetexture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, imagedata);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
}


//compile shaders
var vertexSource = document.getElementById('vertexShader').textContent;
var fragmentSource = document.getElementById('fragmentShader').textContent;
var masterGl;
var layer = {
  id:"baseReflectivity",
  type:"custom",
  minzoom:0,
  maxzoom:18,

  onAdd: function(map, gl) {
    masterGl = gl;
    console.log(gl);
    createTexture(gl);
    
    var vertexShader = gl.createShader(gl.VERTEX_SHADER);
    gl.shaderSource(vertexShader, vertexSource);
    gl.compileShader(vertexShader);
    var compilationLog = gl.getShaderInfoLog(vertexShader);
    console.log('Shader compiler log: ' + compilationLog);
    var fragmentShader = gl.createShader(gl.FRAGMENT_SHADER);
    gl.shaderSource(fragmentShader, fragmentSource);
    gl.compileShader(fragmentShader);
    var compilationLog = gl.getShaderInfoLog(fragmentShader);
    console.log('Shader compiler log: ' + compilationLog);
    this.program = gl.createProgram();
    gl.attachShader(this.program, vertexShader);
    gl.attachShader(this.program, fragmentShader);
    gl.linkProgram(this.program);
    // add this for extra debugging
    if ( !gl.getProgramParameter(this.program, gl.LINK_STATUS) ) {
      var info = gl.getProgramInfoLog(this.program);
      throw new Error('Could not compile WebGL program. \n\n' + info);
    }
    
    this.radar_lat = gl.getUniformLocation(this.program, "radar_lat");
    this.radar_lon = gl.getUniformLocation(this.program, "radar_lon");
    this.azimuths = gl.getUniformLocation(this.program, "azimuths");
    this.scanangle = gl.getUniformLocation(this.program, "scanangle");
    this.gateres = gl.getUniformLocation(this.program, "gateres");
    this.matrixLocation = gl.getUniformLocation(this.program, "u_matrix");
    this.positionLocation = gl.getAttribLocation(this.program, "aPosition");
    this.colorLocation = gl.getAttribLocation(this.program, "aColor");
    this.textureLocation = gl.getUniformLocation(this.program, "u_texture");

    //data buffers
    this.positionBuffer = gl.createBuffer();
    this.colorBuffer = gl.createBuffer();
  },
  render: function(gl, matrix) {
    gl.useProgram(this.program);
    
    const sizeVertices = 2;
    const sizeColors = 1;
    const typeVertices = gl.FLOAT;
    const typeColors = gl.UNSIGNED_BYTE;
    var normalize = true;
    var stride = 0;
    var offset = 0;
    
    gl.uniformMatrix4fv(this.matrixLocation, false, matrix);
    
    if (changingContent) {
      gl.uniform1f(this.scanangle, settings.scanangle);
      gl.uniform1f(this.gateres, settings.gateres);
      gl.uniform1fv(this.azimuths, pageState.azimuths);
      gl.uniform1f(this.radar_lat, settings.rlat);
      gl.uniform1f(this.radar_lon, settings.rlon);
      gl.uniform1i(this.textureLocation, 1); // Corresponds to gl.TEXTURE1 used in gl.activateTexture

      gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, pageState.positions, gl.STREAM_DRAW);
      gl.enableVertexAttribArray(this.positionLocation);
      gl.vertexAttribPointer(this.positionLocation, sizeVertices, typeVertices, normalize, stride, offset);
    
      gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, pageState.colors, gl.STREAM_DRAW);
      gl.enableVertexAttribArray(this.colorLocation);
      gl.vertexAttribPointer(this.colorLocation, sizeColors, typeColors, normalize, stride, offset);      
    }

    gl.drawArrays(gl.TRIANGLE_STRIP, offset, pageState.colors.length);
    
    changingContent = false;
  }
}

function dataStore() {
  return {
    positions:null,
    colors:null,
    azimuths:null
  }
}

var pageState = dataStore();

var paintingFinished = true;
var paintingFinishedTime = new Date().getTime();
async function display() {
  const url = `data/radar/test_numpy_zarr/test_${time}_${scan}.zarr`;
  const { pos, colors, azimuths } = await generateVertices(url);
  
  pageState.positions = pos;
  pageState.colors = colors;
  pageState.azimuths = azimuths;
  changingContent = true;
  if (start == 1) {
    map.addLayer(layer);
  } else {
    map.triggerRepaint();
  }
  paintingFinished = true;
  paintingFinishedTime = new Date().getTime();
}

var t = new Date().getTime();
function onKeyPress(event) {
	// console.log(event.key);
  if (!paintingFinished || new Date().getTime() - paintingFinishedTime < 10) {
    return;
  }

  switch(event.key) {
    case "ArrowDown":
      scan -= 1;
      break;
    case "ArrowUp":
      scan += 1;
      break;
    case "ArrowLeft":
      time -= 1;
      break;
    case "ArrowRight":
      time += 1;
      break;
  }
  // console.log(scan, time);
  if (scan >= 0 && scan <= 15 && time >= 0 && time <= 27) {
    paintingFinished = false;
    start = false;
    display();
    // console.log("display finished");
  } else {
    scan = Math.min(Math.max(scan, 0), 15);
    time = Math.min(Math.max(time, 0), 27);
  }
}

document.addEventListener("keydown", onKeyPress); 
map.on("load", display);