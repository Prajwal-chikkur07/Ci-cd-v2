use actix_web::{web, App, HttpServer, HttpResponse};
use serde_json::json;

async fn index() -> HttpResponse {
    HttpResponse::Ok().json(json!({
        "message": "Hello from Actix-web",
        "status": "running"
    }))
}

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(json!({
        "status": "healthy"
    }))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("Starting server on 0.0.0.0:8080");
    
    HttpServer::new(|| {
        App::new()
            .route("/", web::get().to(index))
            .route("/health", web::get().to(health))
    })
    .bind("0.0.0.0:8080")?
    .run()
    .await
}
