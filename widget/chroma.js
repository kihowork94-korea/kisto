// 검은 배경 캐릭터 영상을 WebGL로 실시간 투명 처리한다.
// 가장 밝은 채널 값이 key.low 이하면 완전 투명, key.high 이상이면 불투명,
// 그 사이는 부드럽게 섞는다 (머리카락·빛나는 날개 가장자리가 자연스럽게 남도록).
// 미리 알파 채널 영상으로 변환하지 않으므로 검은 배경 mp4를 넣기만 하면 된다.

const VERTEX = `
attribute vec2 pos;
varying vec2 uv;
uniform vec2 crop; // (위쪽 잘라낼 비율, 아래쪽 잘라낼 비율)
void main() {
  vec2 t = (pos + 1.0) * 0.5;
  uv = vec2(t.x, crop.x + (1.0 - t.y) * (1.0 - crop.x - crop.y));
  gl_Position = vec4(pos, 0.0, 1.0);
}`;

const FRAGMENT = `
precision mediump float;
varying vec2 uv;
uniform sampler2D frame;
uniform vec2 key;
void main() {
  vec3 c = texture2D(frame, uv).rgb;
  float a = smoothstep(key.x, key.y, max(c.r, max(c.g, c.b)));
  // 검은 배경 위에 찍힌 색은 이미 "원래 색 × 알파" 상태라 그대로 premultiplied 색이다.
  // 한 번 더 곱하면 가장자리가 검게 뜬다. 배경 쪽 잔여 밝기만 알파로 눌러준다.
  gl_FragColor = vec4(min(c, vec3(a)), a);
}`;

class ChromaCharacter {
  constructor(canvas, video, { key, crop }) {
    this.canvas = canvas;
    this.video = video;
    this.key = key;
    this.crop = crop;
    this.probe = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
    this.probe.canvas.width = this.probe.canvas.height = 1;

    const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true });
    this.gl = gl;
    const program = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, VERTEX], [gl.FRAGMENT_SHADER, FRAGMENT]]) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, src);
      gl.compileShader(shader);
      gl.attachShader(program, shader);
    }
    gl.linkProgram(program);
    gl.useProgram(program);

    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const pos = gl.getAttribLocation(program, "pos");
    gl.enableVertexAttribArray(pos);
    gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

    gl.uniform2f(gl.getUniformLocation(program, "key"), key.low, key.high);
    gl.uniform2f(gl.getUniformLocation(program, "crop"), crop.top, crop.bottom);

    gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

    this._draw = this._draw.bind(this);
    requestAnimationFrame(this._draw);
  }

  /** 잘라낸 뒤의 세로/가로 비율. 캔버스 크기를 정할 때 쓴다. */
  aspect() {
    const { videoWidth: w, videoHeight: h } = this.video;
    return (h * (1 - this.crop.top - this.crop.bottom)) / w;
  }

  _draw() {
    const { gl, video, canvas } = this;
    if (video.readyState >= 2) {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, video);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    requestAnimationFrame(this._draw);
  }

  /** 캔버스 위 (x, y) 지점이 캐릭터의 불투명한 부분인지 — 클릭 통과 판정용. */
  isOpaqueAt(x, y) {
    const { video, canvas, crop } = this;
    if (video.readyState < 2) return false;
    const rect = canvas.getBoundingClientRect();
    const u = (x - rect.left) / rect.width;
    const v = (y - rect.top) / rect.height;
    if (u < 0 || u > 1 || v < 0 || v > 1) return false;
    const sx = u * video.videoWidth;
    const sy = (crop.top + v * (1 - crop.top - crop.bottom)) * video.videoHeight;
    this.probe.drawImage(video, sx, sy, 1, 1, 0, 0, 1, 1);
    const [r, g, b] = this.probe.getImageData(0, 0, 1, 1).data;
    return Math.max(r, g, b) / 255 > (this.key.low + this.key.high) / 2;
  }
}

window.ChromaCharacter = ChromaCharacter;
