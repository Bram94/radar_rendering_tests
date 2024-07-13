
function radians(deg) {
  return (Math.PI/180.)*deg;
}
// Modulo for which mod(-1, 360) = 359 instead of -1 as it is for % operator
function mod(n, m) {
  return ((n % m) + m) % m;
}
function anglediff(a1, a2) {
  return mod(mod(a2-a1+180, 360)-180, 360);
}


// In the past this coordinate transformation took place at the GPU, but this lead to some position errors, presumably due to floating point inaccuracies in trigonometric functions. 
// Also, this GPU implementation didn't use the ellipsoidal azimuthal equidistant projection that is used below, which was another source of slight position errors.
// And although this function is relatively slow, thanks to large reductions in the number of calculations of vertex coordinates, this is now not at all an issue anymore.
const ke = 4./3.;
const Re = 6371000.;
var proj, theta;
function calculatePosition(az, sr) {
  az = radians(az);
  const h = Math.sqrt(Math.pow(sr, 2.)+Math.pow(ke*Re, 2.)+2.*ke*Re*sr*Math.sin(theta));
  const gr = ke*Re*Math.asin(sr*Math.cos(theta)/h);
  
  const x = gr*Math.sin(az);
  const y = gr*Math.cos(az);
    
  const out = proj.inverse([x, y]);
  const lon = radians(out[0]);
  const lat = radians(out[1]);
      
  const mx = 0.5 + 0.5*lon/Math.PI;
  const my = 0.5 - 0.5*Math.log(Math.tan(Math.PI/4. + lat/2.))/Math.PI;
  return { x:mx, y:my };
}


var stored_data = {};

var values, attrs, pos, texpos, azimuths, az, az_previous, i1, i2, az1, az2, d1, d2, x, y, bl, tl, br, tr;
export async function generateVertices(settings) {
  const t = new Date().getTime();
  
  if (!(settings.url in stored_data)) {
    //get file from server
    const z = await zarr.openArray({ store: "http://localhost:8080/", path: settings.url, mode: "r" });
    values = (await z.get()).data;
    attrs = await z.attrs.asObject();
    stored_data[settings.url] = [values, attrs];
  } else {
    values = stored_data[settings.url][0];
    attrs = stored_data[settings.url][1];
  }
  console.log(new Date().getTime()-t, "fetch and open zarr");
  
  const nazs = attrs.nazs;
  const ngates = attrs.ngates;
  const gateres = attrs.gate_spacing;
  const firstgate = Math.max(attrs.first_gate-gateres/2., 0.01);
  proj = proj4(`+proj=aeqd +lat_0=${settings.rlat} +lon_0=${settings.rlon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs`);
  theta = radians(attrs.scanangle);
  
  const azs = attrs.azimuths;
  var azs_edge = [];
  var anglediffs = [];
  for (var i=0; i<nazs; i++) {
    az = (i == 0) ? (azs[0]+360+azs[nazs-1])/2 : (azs[i-1]+azs[i])/2
    az_previous = (i == 0) ? (azs[nazs-2]+azs[nazs-1])/2 : azs_edge[i-1];
    azs_edge.push(az);
    anglediffs.push(anglediff(az_previous, az));
  }
    
  const update_vertices = true;
  // Use 1 pair of triangles per 50 km of radial. Using just 1 pair for the full radial leads to some position errors, since in
  // Mercator projection a radial is not fully straight
  const nj = Math.ceil(ngates*gateres/50e3);
  if (update_vertices) {
    const totalVertices = nazs*6*nj;
    pos = new Float32Array(2*totalVertices);
    texpos = new Float32Array(2*totalVertices);
  }
  
  // Calculate vertex coordinates of the triangles, and use the fact that the triangles have many overlapping vertices, to minimise the number of calculations. 
  // Also, since running calculatePosition is relatively expensive it's important to limit calling it as much as possible. For this reason, in case of high 
  // azimuthal resolution (like NEXRAD's 0.5 degrees), half of the vertex coordinates is calculated by linearly interpolating between those for surrounding radials.
  var vertices = [];
  const imax = Math.ceil((nazs+1)/2);
  for (var i=0; i<imax; i++) {
    i1 = 2*i-1;
    i2 = Math.min(2*i, nazs-1);
    az1 = azs_edge[i1];
    az2 = azs_edge[i2];
    d1 = anglediffs[i1];
    d2 = anglediffs[i2];

    vertices.push([]); vertices.push([]);
    for (var j=0; j<nj+1; j++) {
      vertices[i2].push(calculatePosition(az2, firstgate+j/nj*ngates*gateres));
      if (i > 0 && i2 != i1) {
        if (d1 < 0.6 && d2 < 0.6) {
          x = (d1*vertices[i2-2][j].x+d2*vertices[i2][j].x)/(d1+d2);
          y = (d1*vertices[i2-2][j].y+d2*vertices[i2][j].y)/(d1+d2);
          vertices[i1].push({ x:x, y:y });
        } else {
          vertices[i1].push(calculatePosition(az1, firstgate+j/nj*ngates*gateres));
        }
      }
    }
  }

  var n = 0;  
  for (var i=0; i<nazs; i++) {
    for (var j=0; j<nj; j++) {
      bl = vertices[i][j];
      br = vertices[(i+1) % nazs][j];
      tl = vertices[i][j+1];
      tr = vertices[(i+1) % nazs][j+1];
      
      pos[2*n] = bl.x;
      pos[2*n+1] = bl.y;
      pos[2*n+2] = pos[2*n+6] = br.x;
      pos[2*n+3] = pos[2*n+7] = br.y;
      pos[2*n+4] = pos[2*n+8] = tl.x;
      pos[2*n+5] = pos[2*n+9] = tl.y;
      pos[2*n+10] = tr.x;
      pos[2*n+11] = tr.y;

      texpos[2*n] = j/nj*ngates;
      texpos[2*n+1] = i;
      texpos[2*n+2] = texpos[2*n+6] = j/nj*ngates;
      texpos[2*n+3] = texpos[2*n+7] = i+1;
      texpos[2*n+4] = texpos[2*n+8] = (j+1)/nj*ngates;
      texpos[2*n+5] = texpos[2*n+9] = i;
      texpos[2*n+10] = (j+1)/nj*ngates;
      texpos[2*n+11] = i+1;
      
      n += 6;
    }
  }
  
  console.log(new Date().getTime()-t, "loop");
  const shape = [nazs, ngates];
  return { pos, texpos, values, shape, update_vertices };
}