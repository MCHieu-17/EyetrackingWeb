# k6 summary

scenario: session_contents

- http_req_waiting: avg=19.826, min=4.946, med=21.553, max=25.241, p(90)=24.914, p(95)=25.219, p(99)=25.236
- http_req_failed: rate=0.000
- http_req_sending: p(90)=0.058, p(95)=0.070, p(99)=0.074, avg=0.046, min=0.012, med=0.043, max=0.075
- iterations: count=20.000, rate=4.523
- http_req_duration{expected_response:true}: max=25.356, p(90)=25.064, p(95)=25.339, p(99)=25.353, avg=19.968, min=4.995, med=21.700
- vus: min=1.000, max=1.000
- http_req_receiving: p(99)=0.231, avg=0.097, min=0.037, med=0.089, max=0.256, p(90)=0.114, p(95)=0.130
- http_req_blocked: p(99)=0.136, avg=0.024, min=0.005, med=0.011, max=0.136, p(90)=0.027, p(95)=0.135
- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.096, p(90)=0.000, p(95)=0.005, p(99)=0.078
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration: avg=19.968, min=4.995, med=21.700, max=25.356, p(90)=25.064, p(95)=25.339, p(99)=25.353
