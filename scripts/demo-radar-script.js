import { generateVertices } from './generateVerticesRadarDemo.js';

var scan = 0;
var time = 10;
var start = true;
var changingContent = false;

var settings = {};
settings["rlat"] = 35.33335;
settings["rlon"] = -97.27776;

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
.setLngLat([-97.8316988535486, 35.6428070716210])
.addTo(map)

new mapboxgl.Marker()
.setLngLat([-98.78664631025524, 38.06854215296778])
.addTo(map)

new mapboxgl.Marker()
.setLngLat([-98.06215215881625, 34.98763436419662])
.addTo(map)

new mapboxgl.Marker()
.setLngLat([-98.36821019014079, 32.648868509522835])
.addTo(map)


function createPaletteTexture(gl) {
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
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
}

function createImageTexture(gl) {
  var imageTex = gl.createTexture();
  gl.activeTexture(gl.TEXTURE2);
  gl.bindTexture(gl.TEXTURE_2D, imageTex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.ALPHA, 1, 1, 0, gl.ALPHA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 255, 255]));
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
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
    createPaletteTexture(gl);
    createImageTexture(gl);
    
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
    
    this.data_shape = gl.getUniformLocation(this.program, "data_shape");
    
    this.matrixLocation = gl.getUniformLocation(this.program, "u_matrix");
    this.positionLocation = gl.getAttribLocation(this.program, "aPosition");
    this.texpositionLocation = gl.getAttribLocation(this.program, "aTexPosition");
    
    this.paletteLoc = gl.getUniformLocation(this.program, "u_palette");
    this.imageLoc = gl.getUniformLocation(this.program, "u_image");
    
    gl.useProgram(this.program);
    // tell it to use texture units 1 and 2 for the palette and image. These correspond to gl.TEXTURE1 and gl.TEXTURE2 used in gl.activeTexture.
    // Texture 0 also exists, but using this leads to the need of rebinding the texture on every call of layer.render.
    gl.uniform1i(this.paletteLoc, 1);
    gl.uniform1i(this.imageLoc, 2);

    //data buffers
    this.positionBuffer = gl.createBuffer();
    this.texpositionBuffer = gl.createBuffer();
  },
  render: function(gl, matrix) {
    gl.useProgram(this.program);
            
    gl.uniformMatrix4fv(this.matrixLocation, false, matrix);
    
    if (changingContent) {
      gl.uniform2f(this.data_shape, pageState.shape[1], pageState.shape[0]);

      const sizeVertices = 2;
      const typeVertices = gl.FLOAT;
      const normalize = false;
      const stride = 0;
      var offset = 0; // Must be variable somehow
      
      if (pageState.update_vertices) {
        gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, pageState.positions, gl.STREAM_DRAW);
        gl.enableVertexAttribArray(this.positionLocation);
        gl.vertexAttribPointer(this.positionLocation, sizeVertices, typeVertices, normalize, stride, offset);
        
        gl.bindBuffer(gl.ARRAY_BUFFER, this.texpositionBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, pageState.texpositions, gl.STREAM_DRAW);
        gl.enableVertexAttribArray(this.texpositionLocation);
        gl.vertexAttribPointer(this.texpositionLocation, sizeVertices, typeVertices, normalize, stride, offset);
      }
    
      gl.activeTexture(gl.TEXTURE2);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.ALPHA, pageState.shape[1], pageState.shape[0], 0, gl.ALPHA, gl.UNSIGNED_BYTE, pageState.values);
    }

    gl.drawArrays(gl.TRIANGLES, offset, pageState.positions.length/2);
    
    changingContent = false;
  }
}

function dataStore() {
  return {
    positions:null,
    texpositions:null,
    values:null,
    shape:null,
    update_vertices:null
  }
}

var pageState = dataStore();

var paintingFinished = true;
var paintingFinishedTime = new Date().getTime();
async function display() {
  settings.url = `data/radar/test_numpy_zarr_flat/test_${time}_${scan}.zarr`;
  const { pos, texpos, values, shape, update_vertices } = await generateVertices(settings);

  pageState.positions = pos;
  pageState.texpositions = texpos;
  pageState.values = values;
  pageState.shape = shape;
  pageState.update_vertices = update_vertices;
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
var animating = false;
function onKeyPress(event) {
	// console.log(event.key);
  if (!paintingFinished || new Date().getTime() - paintingFinishedTime < 0) {
    return;
  }

  console.log(event.key);
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
    case " ":
      animating = !animating;
      if (animating) {
        return animate();
      }
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

var looptime = 0;
function animate() {
  if (paintingFinished && new Date().getTime() - paintingFinishedTime > 0) {
    if (time < 27) {
      time += 1;
    } else {
      time = 0;
      console.log(new Date().getTime() - looptime);
      looptime = new Date().getTime();
    }
    paintingFinished = false;
    start = false;
    display();
  }
  if (animating) {
    setTimeout(() => {requestAnimationFrame(animate);}, 1);
  }
}

document.addEventListener("keydown", onKeyPress); 
map.on("load", display);