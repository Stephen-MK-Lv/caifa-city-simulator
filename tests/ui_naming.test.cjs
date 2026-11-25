const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base=path.join(__dirname,'../app/static');
for(const name of fs.readdirSync(base).filter(n=>/\.(js|html)$/.test(n))){
 const text=fs.readFileSync(path.join(base,name),'utf8');
 assert.doesNotMatch(text,/教学|城市会计实验室|月度动态立方体|彩珐(?!市)|>珐<|仿真仿真/,name);
}
const page=fs.readFileSync(path.join(base,'index.html'),'utf8');
assert.match(page,/brand-mark">彩</);assert.match(page,/城市发展仿真/);assert.match(page,/城市发展/);
assert.doesNotMatch(page,/城市发展过程/);
assert.match(fs.readFileSync(path.join(base,'portal.js'),'utf8'),/基于城市发展，动态理解一座城市/);
for(const label of ['业务事件簿','会计凭证簿','资产台账簿','城市发展仿真实验室'])assert.ok(page.includes(label));
assert.doesNotMatch(page,/簿簿|实验室实验室/);
assert.match(fs.readFileSync(path.join(base,'monthly-compact.css'),'utf8'),/background:rgba\(255,254,247,\.72\)/);
console.log('System UI names, icon and subtitle consistency passed.');
