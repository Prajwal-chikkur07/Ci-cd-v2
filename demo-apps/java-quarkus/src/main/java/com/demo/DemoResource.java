package com.demo;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/")
public class DemoResource {

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public Response hello() {
        return new Response("Hello from Quarkus", "running");
    }

    @GET
    @Path("/health")
    @Produces(MediaType.APPLICATION_JSON)
    public HealthResponse health() {
        return new HealthResponse("healthy");
    }

    public static class Response {
        public String message;
        public String status;

        public Response(String message, String status) {
            this.message = message;
            this.status = status;
        }
    }

    public static class HealthResponse {
        public String status;

        public HealthResponse(String status) {
            this.status = status;
        }
    }
}
