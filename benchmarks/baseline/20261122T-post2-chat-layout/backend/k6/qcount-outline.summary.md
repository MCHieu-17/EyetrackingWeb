# k6 summary

scenario: outline

- http_req_waiting: avg=7.791, min=2.493, med=8.391, max=10.536, p(90)=10.207, p(95)=10.324, p(99)=10.494
- http_req_receiving: p(90)=0.274, p(95)=0.395, p(99)=0.400, avg=0.144, min=0.036, med=0.122, max=0.401
- vus: min=1.000, max=1.000
- iterations: count=20.000, rate=4.781
- http_req_blocked: max=0.119, p(90)=0.018, p(95)=0.047, p(99)=0.104, avg=0.018, min=0.004, med=0.011
- http_req_failed: rate=0.000
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.088, p(90)=0.000, p(95)=0.004, p(99)=0.071
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_sending: max=0.074, p(90)=0.053, p(95)=0.063, p(99)=0.071, avg=0.043, min=0.013, med=0.041
- http_req_duration: p(95)=10.485, p(99)=10.650, avg=7.978, min=2.569, med=8.769, max=10.692, p(90)=10.385
- http_req_duration{expected_response:true}: max=10.692, p(90)=10.385, p(95)=10.485, p(99)=10.650, avg=7.978, min=2.569, med=8.769
