pipeline {
  agent any

  environment {
    BACKEND_IMAGE = 'yourdockerhub/student-attendance-backend:latest'
    FRONTEND_IMAGE = 'yourdockerhub/student-attendance-frontend:latest'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Build + Test') {
      steps {
        sh 'python3 -m py_compile backend/app.py'
      }
    }

    stage('Docker Build') {
      steps {
        sh 'docker build -t $BACKEND_IMAGE backend'
        sh 'docker build -t $FRONTEND_IMAGE frontend'
      }
    }

    stage('Docker Push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          sh 'echo $DOCKER_PASS | docker login -u $DOCKER_USER --password-stdin'
          sh 'docker push $BACKEND_IMAGE'
          sh 'docker push $FRONTEND_IMAGE'
        }
      }
    }

    stage('Auto Deploy (docker-compose)') {
      steps {
        sh 'docker compose down || true'
        sh 'docker compose up -d --build'
      }
    }
  }
}
