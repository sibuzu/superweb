/* Publish only browser assets; authoring helpers and source inventory stay local. */
const fs = require('node:fs');
const path = require('node:path');
const target = path.join(__dirname, 'dist');
fs.mkdirSync(path.join(target, 'data'), {recursive: true});
for (const name of ['index.html', 'styles.css', 'app.js', 'favorites-sync.js', 'data/catalog.js', 'data/catalog.json']) {
  fs.copyFileSync(path.join(__dirname, name), path.join(target, name));
}
console.log('Prepared dist/ with 6 browser assets.');
