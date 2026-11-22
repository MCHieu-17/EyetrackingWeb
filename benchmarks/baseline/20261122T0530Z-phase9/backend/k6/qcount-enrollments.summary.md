# k6 summary

scenario: enrollments

- http_req_blocked: p(95)=0.046, p(99)=0.101, avg=0.018, min=0.005, med=0.012, max=0.115, p(90)=0.019
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.869
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.085, p(90)=0.000, p(95)=0.004, p(99)=0.069
- http_req_waiting: avg=4.052, min=1.067, med=4.251, max=4.468, p(90)=4.400, p(95)=4.443, p(99)=4.463
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_duration{expected_response:true}: min=1.114, med=4.410, max=4.669, p(90)=4.582, p(95)=4.615, p(99)=4.658, avg=4.218
- vus: min=1.000, max=1.000
- http_req_duration: p(90)=4.582, p(95)=4.615, p(99)=4.658, avg=4.218, min=1.114, med=4.410, max=4.669
- http_req_sending: avg=0.044, min=0.014, med=0.042, max=0.075, p(90)=0.058, p(95)=0.061, p(99)=0.072
- http_req_receiving: p(99)=0.184, avg=0.122, min=0.033, med=0.124, max=0.185, p(90)=0.166, p(95)=0.180
