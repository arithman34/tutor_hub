output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "note" {
  value = "No ALB / ACM cert here. In the Cloudflare Zero Trust dashboard, set the tunnel's public hostname to this domain -> http://localhost:8000 (the tunnel runs inside the task, so 'localhost' means the api container). Cloudflare issues and terminates TLS at its edge; no certificate to manage here."
}
