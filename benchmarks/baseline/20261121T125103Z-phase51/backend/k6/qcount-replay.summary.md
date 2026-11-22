# k6 summary

scenario: replay

- vus: max=1.000, min=1.000
- http_req_duration{expected_response:true}: avg=43.839, min=18.133, med=42.940, max=79.106, p(90)=51.935, p(95)=53.405, p(99)=73.966
- http_req_receiving: min=0.081, med=0.110, max=0.249, p(90)=0.173, p(95)=0.187, p(99)=0.237, avg=0.121
- http_req_blocked: min=0.004, med=0.012, max=0.112, p(90)=0.020, p(95)=0.044, p(99)=0.098, avg=0.018
- http_req_connecting: med=0.000, max=0.079, p(90)=0.000, p(95)=0.004, p(99)=0.064, avg=0.004, min=0.000
- iterations: rate=4.084, count=20.000
- http_req_waiting: p(99)=73.816, avg=43.670, min=18.012, med=42.770, max=78.957, p(90)=51.792, p(95)=53.256
- http_req_duration: p(99)=73.966, avg=43.839, min=18.133, med=42.940, max=79.106, p(90)=51.935, p(95)=53.405
- http_req_failed: rate=0.000
- http_req_sending: med=0.044, max=0.092, p(90)=0.058, p(95)=0.068, p(99)=0.087, avg=0.047, min=0.018
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
