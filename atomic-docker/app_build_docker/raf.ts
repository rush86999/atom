import raf from 'raf';
const polys: any = {};
raf.polyfill(polys);

// module.exports = polys.requestAnimationFrame;

export default polys.requestAnimationFrame;
