window.onscroll = function() {toggleDisplayBtn()};

function toggleDisplayBtn() {
	gotobtn = document.querySelector("[id=gotobtn]");
  if (document.body.scrollTop > 45 || document.documentElement.scrollTop > 45) {
    gotobtn.classList.remove("display-none");
  } else {
    gotobtn.classList.add("display-none");
  }
}

function gotoTop() {
  document.body.scrollTop = 0;
  document.documentElement.scrollTop = 0;
}

function gotoBottom() {
  window.scrollTo(0,document.body.scrollHeight);
}
