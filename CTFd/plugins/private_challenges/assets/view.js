CTFd._internal.challenge.data = undefined;

// TODO: Remove in CTFd v4.0
CTFd._internal.challenge.renderer = null;

CTFd._internal.challenge.preRender = function() {};

// TODO: Remove in CTFd v4.0
CTFd._internal.challenge.render = null;

CTFd._internal.challenge.postRender = function() {};

CTFd._internal.challenge.submit = function(preview) {
  var challenge_id = parseInt(CTFd.lib.$("#challenge-id").val());
  var submission = CTFd.lib.$("#challenge-input").val();

  var body = {
    challenge_id: challenge_id,
    submission: submission
  };
  var params = {};
  if (preview) {
    params["preview"] = true;
  }

  return CTFd.api.post_challenge_attempt(params, body).then(function(response) {
    if (response.status === 429) {
      // User was ratelimited but process response
      return response;
    }
    if (response.status === 403) {
      // User is not logged in or CTF is paused.
      return response;
    }
    return response;
  });
};

// --------------------------------------------------------------------------------------
// above was copied from dynamic_challenges plugin, make additions below only
// --------------------------------------------------------------------------------------

function toggleLoading(btn) {
    var icon = btn.querySelector('i')
    btn.disabled = !btn.disabled
    icon.classList.toggle('fa-spin')
    icon.classList.toggle('fa-spinner')
}

function handleError(management, r) {
    return r.text()
            .then(text => {
                let message
                try {
                    data = JSON.parse(text)
                    message = data.message
                }
                catch (e) {
                    // not JSON
                    message = text ? text : 'Unexpected error'
                }

                management.querySelector('#private_challenge_error').hidden = false
                management.querySelector('#private_challenge_error').innerText = "Error: " + message
                throw 'escape promise chain'
            })
}


function deployPrivateChallenge(management, serviceName) {
    response = confirm("This will start or reset your team's private challenge.  Do you want to continue?")
    if (!response) {
        return
    }

    let btn = management.querySelector('#private_challenge_button')
    toggleLoading(btn)
    fetch(`/api/private_challenge/${serviceName}`, {"method": "POST"})
        .then(r => {
            toggleLoading(btn)
            if (!r.ok) {
                return handleError(management, r)
            }
            return r.json()
        })
        .then(data => {
            determinePrivateChallengeStatus(management, serviceName)
        })
}

function determinePrivateChallengeStatus(management, serviceName) {

    management.querySelector('#private_challenge_spinner').hidden = false
    management.querySelector('#private_challenge_content').hidden = true
    fetch(`/api/private_challenge/${serviceName}`)
        .then(r => {
            management.querySelector('#private_challenge_spinner').hidden = true
            if (!r.ok) {
                return handleError(management, r)
            }
            return r.json()
        })
        .then(data => {
            management.querySelector('#private_challenge_content').hidden = false

            if (!data.serviceInstanceRunning) {
                management.querySelector('#private_challenge_button_label').innerText = 'Start Challenge'
                management.querySelector('#private_challenge_running_details').hidden = true
            }
            else {
                management.querySelector('#private_challenge_button_label').innerText = 'Reset Challenge'
                management.querySelector('#private_challenge_running_details').hidden = false

                let minutesToLive = Math.max(0, Math.floor(data.secondsToLive / 60))
                management.querySelector('#private_challenge_minutes_to_live').innerText = '' + minutesToLive

                management.querySelector('#private_challenge_url').href = data.serviceUrl
                management.querySelector('#private_challenge_url').innerText = data.serviceUrl
            }
        })
}

