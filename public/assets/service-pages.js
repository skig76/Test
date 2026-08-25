const ruBtn=document.getElementById('ruBtn');
const heBtn=document.getElementById('heBtn');
const descriptionMeta=document.querySelector('meta[name="description"]');

function setLang(lang){
  const isHebrew=lang==='he';
  document.body.classList.toggle('he',isHebrew);
  document.documentElement.lang=isHebrew?'he':'ru';
  document.documentElement.dir=isHebrew?'rtl':'ltr';
  ruBtn.classList.toggle('active',!isHebrew);
  heBtn.classList.toggle('active',isHebrew);
  document.title=isHebrew?document.body.dataset.titleHe:document.body.dataset.titleRu;
  descriptionMeta.content=isHebrew?document.body.dataset.descriptionHe:document.body.dataset.descriptionRu;
}

ruBtn.addEventListener('click',()=>setLang('ru'));
heBtn.addEventListener('click',()=>setLang('he'));
setLang('he');
