/* -------- DARK / LIGHT -------- */
function toggleTheme(){
  document.documentElement.classList.toggle("dark");
  localStorage.theme=document.documentElement.classList.contains("dark")?"dark":"light";
}
if(localStorage.theme==="dark"){
  document.documentElement.classList.add("dark");
}

/* -------- WISHLIST -------- */
function toggleWishlist(id){
  let w=JSON.parse(localStorage.wishlist||"[]");
  w.includes(id)?w=w.filter(x=>x!==id):w.push(id);
  localStorage.wishlist=JSON.stringify(w);
  document.getElementById("wish-"+id).classList.toggle("active");
}

/* -------- QUICK VIEW -------- */
function openQuickView(name,price,img){
  document.getElementById("qv-img").src=img;
  document.getElementById("qv-name").innerText=name;
  document.getElementById("qv-price").innerText="₹"+price;
  document.getElementById("quickView").classList.add("show");
}
function closeQuickView(){
  document.getElementById("quickView").classList.remove("show");
}

/* -------- OFFER POPUP -------- */
if(!sessionStorage.offer){
  setTimeout(()=>{
    document.getElementById("offerPopup").style.display="block";
    sessionStorage.offer=true;
  },1500);
}

