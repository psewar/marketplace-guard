// TEST FIXTURE: a minified frontend plugin as typically found in www/community
const _A="QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5";
function h(s){return s.split("").map(c=>String.fromCharCode(c.charCodeAt(0))).join("")}
customElements.define("x-card",class extends HTMLElement{set hass(h){this.innerHTML=atob(_A).slice(0,3)}});
const fn=new Function("return 1");
