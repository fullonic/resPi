// Set the date we're counting down to
// var countDownDate = new Date("Jan 5, 2021 15:37:11").getTime();

function countDown(cycle_ends_in) {
  // COUNT TIMER FOR AUTO PROGRAM
  var countDownDate = cycle_ends_in;
  console.log("FROM TIMER", cycle_ends_in);

  // Update the count down every 1 second
  var count_down = setInterval(function() {

    // Get today's date and time
    var now = new Date().getTime();

    // Find the distance between now and the count down date
    var distance = countDownDate - now;

    // Time calculations for days, hours, minutes and seconds
    var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    var seconds = Math.floor((distance % (1000 * 60)) / 1000);

    // Display the result in the element with id="demo"
    if (hours < 10) {
      hours = "0" + hours;
    }
    if (minutes < 10) {
      minutes = "0" + minutes;
    }
    if (seconds < 10) {
      seconds = "0" + seconds;
    }
    document.getElementById("timer").innerHTML = hours + ":" +
      minutes + ":" + seconds;

    // If the count down is finished, write some text
    if (distance < 0) {
      clearInterval(count_down);
      document.getElementById("timer").innerHTML = "";
    }
  }, 1000);
};

function stopWatch(started_at, id) {
  // countFrom = new Date(countFrom).getTime();
  var countFrom = started_at;
  var now = new Date(),
    countFrom = new Date(countFrom),
    timeDifference = (now - countFrom);

  var secondsInADay = 60 * 60 * 1000 * 24,
    secondsInAHour = 60 * 60 * 1000;

  days = Math.floor(timeDifference / (secondsInADay) * 1);
  hours = Math.floor((timeDifference % (secondsInADay)) / (secondsInAHour) * 1);
  minutes = Math.floor(((timeDifference % (secondsInADay)) % (secondsInAHour)) / (60 * 1000) * 1);
  seconds = Math.floor((((timeDifference % (secondsInADay)) % (secondsInAHour)) % (60 * 1000)) / 1000 * 1);
  document.getElementById("timer").innerHTML = (hours ? (hours > 9 ? hours : "0" + hours) : "00") + ":" + (minutes ? (minutes > 9 ? minutes : "0" + minutes) : "00") + ":" + (seconds > 9 ? seconds : "0" + seconds)

  clearTimeout(stopWatch.interval);
  stopWatch.interval = setTimeout(function() {
    stopWatch(countFrom);
  }, 1000);
}