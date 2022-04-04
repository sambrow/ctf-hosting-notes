# How to Host CTF Web Challenges


These are things we've learned about hosting CTF web challenges using Google Cloud Run on Google Cloud Platform (GCP).

## Requirements/Limitations
- The challenge must be a web application.
- This technique does not support arbitrary protocols/ports.
- Your web application can listen on any port internally but it will be exposed to the Internet on port 443 via `https://`.
- The challenge must be containerized as a Docker image.
- You must have a google cloud account.
- You must install the gcloud command line tooling.
- It is easiest if your web application requires no server-side session/state.
  - With some effort, you can set up a Cloud Run service to talk to a Google-hosted REDIS instance but it is well worth some effort to see if you can avoid the need for this.
  - For example, you might be able to keep the entire session state in a Cookie using something like JWT.

## What Should I Do First?

- If your CTF event planning is far enough along, you should seek [sponsorship from GCP](https://services.google.com/fb/forms/ctfsponsorship/).
  - If you get sponsored, you'll get some free google cloud money to help host your event.
- Learn Docker.  There are lots of great resources online.  Install Docker locally and run through some online tutorials.
  - Here is at least one way [to get started](https://www.youtube.com/watch?v=3c-iBn73dDE).
- Sign up for [Google Cloud Platform (GCP)](https://console.cloud.google.com/). When I first did this with my personal Google account, it gave me $300 free cloud bucks and a few months to spend them.
  - This is a wonderful way to play around with the bits of GCP that are interesting to you.
  - Note: There are likely too many facets to try to learn everything in a few months.
  - You'll encounter a few of them in these instructions and the rest will just be purposefully ignored.
- [Setup a Google Cloud "Project"](https://cloud.google.com/resource-manager/docs/creating-managing-projects).
  - Inside such a "project" is where you will do everything related to your CTF challenge hosting.
  - You can create multiple projects if you like, but the things you do inside one will not affect or be seen by the other. 
- [Install the gcloud CLI (command line interface)](https://cloud.google.com/sdk/docs/install) onto your computer.
  - As we progress in the instructions, you'll see that you can often set up something in GCP just by using the Web UI.  However, it is well worth getting used to the gcloud CLI since it allow for easier automation such as with bash scripts. 
  - At some point you'll run `gloud init`.  This is where you will:
    - authenticate gcloud so that it has permissions to "talk to" your GCP project
    - select which "project" you want gcloud to talk to by default (it is easy to switch between projects and even between multiple google accounts if needed)

## My First Web Challenge

Here, we'll create a trivial web challenge and deploy it to Google Cloud Run.

### Challenge Application Source Files

See the `my-first-web-challenge` folder in this repository for the files cited here.

You'll want [nodejs installed](https://nodejs.org/en/download/) if you want to follow along with all the steps here.

Here are the files that make up the source of the challenge app.

[package.json]
```
{
  "name": "my-first-web-challenge",
  "version": "1.0.0",
  "description": "",
  "main": "index.js",
  "scripts": {
    "test": "echo \"Error: no test specified\" && exit 1"
  },
  "author": "",
  "license": "ISC",
  "dependencies": {
    "express": "^4.17.3"
  }
}
```

[package-lock.json]
This file is created automatically when you first run `npm install` (see below).  You generally do want this file to be under source control.


[index.js]
```
let express = require('express');
let app = express();

app.get('/', function(req, res) {
    res.sendFile(__dirname + '/index.html')
});

let port = 8000;
let server = app.listen(port);
console.log('Local server running on port: ' + port);
```

[index.html]
```
<html>
<body>
<p>This is my first html page.  Not much to see here.</p>
<!-- flag{wh4t_m4d3_y0u_l00k_h3r3?} -->
</body>
</html>
```

We won't be teaching you how to use node or the express library but there are 
lots of great resources online.

### Run the Challenge Locally (without Docker)

First bring up a terminal window and cd into the `my-first-web-challenge` folder.

Run this command:

`npm install`

`npm` is part of nodejs.  This will study package.json and download the express library and its dependencies into a folder named `node_modules` (which will be created).

You might see output like this:

```
added 50 packages, and audited 51 packages in 546ms

2 packages are looking for funding
  run `npm fund` for details

found 0 vulnerabilities
```

And now you'll notice a `node_modules` folder has been created.

**Note**: You should always add `node_modules` to a .gitignore file in your git repository.  This will prevent the contents of this folder from being added to source control.

We can now run the application:

`node index.js`

You should see:
`Local server running on port: 8000`

**Note**: This assumes this port is free on your computer.  Feel free to edit `index.js` to use another port.

Now if you open your web browser to this link:

[http://localhost:8000/](http://localhost:8000/)

and you should see something like:

![img.png](media/my-first-web-challenge-app.png)

Of course, if you right-click inside the page and select View Page Source you'll see the flag:

![img.png](media/my-first-web-challenge-view-source.png)

You can press `Control+C` in the terminal window to stop the application.

### Run the Challenge Using Docker

In order to container our challenge application, we'll need a `Dockerfile`.

[Dockerfile]
```
FROM node:12

RUN mkdir -p /ctf/app
WORKDIR /ctf/app

COPY ./package.json ./
COPY ./package-lock.json ./
RUN npm install

COPY ./index.js ./
COPY ./index.html ./
EXPOSE 8000

CMD ["node", "index.js"]
```

[.dockerignore] (not really needed in this project but might be useful in a more complex project)
```
# files to not include in the image
Dockerfile
docker-compose.yml
node_modules
```

It is not our intention to teach you Docker but a couple items here is worth pointing out.

Note that the `EXPOSE 8000` line is purely decorative.  Docker completely ignores it.  It is mainly there to help to reader know that the application will be listening on a certain port.

Also, notice this copies the `package.json` and `package-lock.json` files and then runs `npm install`.

Then afterward, it copies `index.js` and `index.html`.

Why not just copy **everything** up front and then run `npm install`?

Because Docker keeps track of the state of your image after every line of the Dockerfile.

If you are rebuilding an image and Docker can convince itself that all the inputs up to a certain line have not changed, then it'll skip those steps and just use its cached status.

So, if you copied everything up front, then any edit your make to `index.js` or `index.html` will cause `npm install` to re-run when you build the image.

In contrast, in the above `Dockerfile`, edits to these files will not cause npm install to run because none of the files cited before that line will have changed.



We can now build our docker image:

```docker build -t my-first-web-challenge:1.0 .```

This tells docker to build an image with the name `my-first-web-challenge` and the tag `1.0`.
The `.` at the end tells it to study the `Dockerfile` in the current directory.

You might get output like this:

```
[+] Building 48.3s (13/13) FINISHED
 => [internal] load build definition from Dockerfile                                                                                                                                                                         0.0s
 => => transferring dockerfile: 243B                                                                                                                                                                                         0.0s
 => [internal] load .dockerignore                                                                                                                                                                                            0.0s
 => => transferring context: 119B                                                                                                                                                                                            0.0s
 => [internal] load metadata for docker.io/library/node:12                                                                                                                                                                   1.5s
 => [1/8] FROM docker.io/library/node:12@sha256:461c7f8b5e042fa7f47620cbee7772e76ce3fa0891edaab29bf7ebf0e84b9a1a                                                                                                            42.4s
 => => resolve docker.io/library/node:12@sha256:461c7f8b5e042fa7f47620cbee7772e76ce3fa0891edaab29bf7ebf0e84b9a1a                                                                                                             0.0s
 => => sha256:543479162c86f09f3dd624d4b79bc52861431a62fd96eb2ee0727c395cc0d99e 7.69kB / 7.69kB                                                                                                                               0.0s
 => => sha256:0030cc4ce25ce472fe488839def15ec8f2227bb916461b518cf534073c019a86 45.43MB / 45.43MB                                                                                                                             8.4s
 => => sha256:461c7f8b5e042fa7f47620cbee7772e76ce3fa0891edaab29bf7ebf0e84b9a1a 776B / 776B                                                                                                                                   0.0s
 => => sha256:7aeb3a7feab20a6e4e38c3d4745977ce2cd4dec48c84612b1617f0813065f617 2.21kB / 2.21kB                                                                                                                               0.0s
 => => sha256:7ab54d469df647484a8ae344911382d9b4412045d3c0f6536e7442858952cc68 11.30MB / 11.30MB                                                                                                                             2.2s
 => => sha256:0c84a1692804545a237be30579f35e501652cab9a2d8babe2693e66e653c706f 4.34MB / 4.34MB                                                                                                                               1.5s
 => => sha256:628acdaf85032c817e9eb7f4749b887f3733c8c590d2e3c2f396f2051406557f 49.77MB / 49.77MB                                                                                                                            13.1s
 => => sha256:cd55abb6ddd3a9acde3855d39958c460e6fa36b3008d6a6206408c133ab96427 214.47MB / 214.47MB                                                                                                                          31.0s
 => => sha256:561384047eedda5a3ac1d331766ef6303c5154f1a759b63e27ac93e0c12721c9 4.19kB / 4.19kB                                                                                                                               8.5s
 => => extracting sha256:0030cc4ce25ce472fe488839def15ec8f2227bb916461b518cf534073c019a86                                                                                                                                    2.1s
 => => sha256:0108341960c8b322c6e8fbad210fc42ef2e725b01b6d249fb171b054f3a3dfe2 23.70MB / 23.70MB                                                                                                                            13.1s
 => => extracting sha256:7ab54d469df647484a8ae344911382d9b4412045d3c0f6536e7442858952cc68                                                                                                                                    0.4s
 => => extracting sha256:0c84a1692804545a237be30579f35e501652cab9a2d8babe2693e66e653c706f                                                                                                                                    0.2s
 => => sha256:c230c13456fd6acc4074095364629904055974f15859a636e4b02d673dcaf903 2.34MB / 2.34MB                                                                                                                              13.7s
 => => sha256:6a4a51acaaf962d42394bbf97f28e5a8d30e001b2642d8151cabe925e3e10b5c 463B / 463B                                                                                                                                  13.4s
 => => extracting sha256:628acdaf85032c817e9eb7f4749b887f3733c8c590d2e3c2f396f2051406557f                                                                                                                                    2.4s
 => => extracting sha256:cd55abb6ddd3a9acde3855d39958c460e6fa36b3008d6a6206408c133ab96427                                                                                                                                    8.6s
 => => extracting sha256:561384047eedda5a3ac1d331766ef6303c5154f1a759b63e27ac93e0c12721c9                                                                                                                                    0.1s
 => => extracting sha256:0108341960c8b322c6e8fbad210fc42ef2e725b01b6d249fb171b054f3a3dfe2                                                                                                                                    1.5s
 => => extracting sha256:c230c13456fd6acc4074095364629904055974f15859a636e4b02d673dcaf903                                                                                                                                    0.1s
 => => extracting sha256:6a4a51acaaf962d42394bbf97f28e5a8d30e001b2642d8151cabe925e3e10b5c                                                                                                                                    0.0s
 => [internal] load build context                                                                                                                                                                                            0.0s
 => => transferring context: 32.80kB                                                                                                                                                                                         0.0s
 => [2/8] RUN mkdir -p /ctf/app                                                                                                                                                                                              0.9s
 => [3/8] WORKDIR /ctf/app                                                                                                                                                                                                   0.0s
 => [4/8] COPY ./package.json ./                                                                                                                                                                                             0.0s
 => [5/8] COPY ./package-lock.json ./                                                                                                                                                                                        0.0s
 => [6/8] RUN npm install                                                                                                                                                                                                    3.1s
 => [7/8] COPY ./index.js ./                                                                                                                                                                                                 0.0s
 => [8/8] COPY ./index.html ./                                                                                                                                                                                               0.0s
 => exporting to image                                                                                                                                                                                                       0.1s
 => => exporting layers                                                                                                                                                                                                      0.1s
 => => writing image sha256:4cc2c043a3814c31034c75f215ec5184e1df86bc91462dacc71d32d008b9470e                                                                                                                                 0.0s
 => => naming to docker.io/library/my-first-web-challenge:1.0                                                                                                                                                                0.0s

Use 'docker scan' to run Snyk tests against images to find vulnerabilities and learn how to fix them
```

We can now ask docker to list all the images and this one should now be included in the list output.

`docker images`

Possible output:

```
REPOSITORY               TAG       IMAGE ID       CREATED         SIZE
my-first-web-challenge   1.0       4cc2c043a381   3 minutes ago   920MB
```

Now that we have created an image, we can run it.  This will create a container from the image.

`docker run --rm -p 7000:8000 --name fun-app my-first-web-challenge:1.0`

- `--rm` tells Docker to remove the container that was created after it stops
  - this is not really needed but helps reduce clutter by reducing the count of Docker containers lying around
- `-p 7000:8000` causes Docker to listen for traffic on port 7000 and map it to port 8000 inside the container
  - this mainly drives home the point that you have to specify both an external and internal port or else no traffic will reach your application
- `--name fun-app` names the newly-created container `fun-app`
  - if you don't specify a name, docker will make up one for you
- `my-first-web-challenge:1.0` the image name and tag 

Again you should see output like:

```
Local server running on port: 8000
```

You can now access the application using this link:

[http://localhost:7000/](http://localhost:7000/)

and it should show just as before.

In another terminal window run:

`docker ps`

You should see output like this:

```
CONTAINER ID   IMAGE                        COMMAND                  CREATED         STATUS         PORTS                    NAMES
c879bb129966   my-first-web-challenge:1.0   "docker-entrypoint.s…"   7 minutes ago   Up 7 minutes   0.0.0.0:7000->8000/tcp   fun-app
```

To stop the application, you can use the Docker Dashboard UI or run this command:

`docker stop fun-app`

Note: You might be also able to stop the application by pressing Control+C in the terminal window you used to start it. However, I'm not certain this is guaranteed to always work.


