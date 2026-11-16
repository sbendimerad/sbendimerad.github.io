/* Interactive quizzes: every .sb-quiz-q div holds one question (data-answer = index of the right
   option, from 0), a list of options and an explanation. Click an option to check it.
   No account, no storage, no tracking. */
(function () {
  function init() {
    var questions = Array.prototype.slice.call(document.querySelectorAll(".sb-quiz-q"));
    if (!questions.length) return;
    var scoreBox = document.querySelector(".sb-quiz-score");
    var answered = 0, correct = 0;

    function updateScore() {
      if (!scoreBox) return;
      if (answered < questions.length) {
        scoreBox.textContent = "Answered " + answered + " of " + questions.length;
        return;
      }
      scoreBox.innerHTML = "";
      var strong = document.createElement("strong");
      strong.textContent = "Your score: " + correct + " / " + questions.length + ". ";
      scoreBox.appendChild(strong);
      scoreBox.appendChild(document.createTextNode(
        correct === questions.length ? "Perfect!" :
        correct >= questions.length / 2 ? "Well done. Read the explanations of the ones you missed." :
        "Have another look at the lesson, then try again."));
      var again = document.createElement("button");
      again.type = "button";
      again.className = "sb-quiz-again";
      again.textContent = "Try again";
      again.addEventListener("click", reset);
      scoreBox.appendChild(again);
    }

    function reset() {
      answered = 0; correct = 0;
      questions.forEach(function (q) {
        q.classList.remove("is-answered");
        q.querySelectorAll(".sb-quiz-options li").forEach(function (li) {
          li.classList.remove("is-right", "is-wrong");
          li.setAttribute("aria-disabled", "false");
        });
        var ex = q.querySelector(".sb-quiz-explain");
        if (ex) ex.hidden = true;
      });
      updateScore();
      questions[0].scrollIntoView({ behavior: "smooth", block: "start" });
    }

    questions.forEach(function (q) {
      var right = parseInt(q.getAttribute("data-answer"), 10);
      var options = Array.prototype.slice.call(q.querySelectorAll(".sb-quiz-options li"));
      var explain = q.querySelector(".sb-quiz-explain");
      if (explain) explain.hidden = true;
      options.forEach(function (li, i) {
        li.setAttribute("role", "button");
        li.setAttribute("tabindex", "0");
        function choose() {
          if (q.classList.contains("is-answered")) return;
          q.classList.add("is-answered");
          answered += 1;
          if (i === right) correct += 1;
          li.classList.add(i === right ? "is-right" : "is-wrong");
          options[right].classList.add("is-right");
          options.forEach(function (o) { o.setAttribute("aria-disabled", "true"); });
          if (explain) {
            explain.hidden = false;
            explain.setAttribute("aria-live", "polite");
            var verdict = explain.querySelector(".sb-quiz-verdict");
            if (!verdict) {
              verdict = document.createElement("strong");
              verdict.className = "sb-quiz-verdict";
              explain.insertBefore(verdict, explain.firstChild);
            }
            verdict.textContent = i === right ? "Correct. " : "Not quite. ";
          }
          updateScore();
        }
        li.addEventListener("click", choose);
        li.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); }
        });
      });
    });
    updateScore();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
