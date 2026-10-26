# Render (cloud): builds the Java backend and serves the API + website from one container.
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app/backend
COPY backend/pom.xml .
RUN mvn -q -B dependency:go-offline
COPY backend/src ./src
RUN mvn -q -B package -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/backend/target/mess.jar backend/mess.jar
COPY docs ./docs
ENV HOST=0.0.0.0
CMD ["java", "-jar", "backend/mess.jar"]
