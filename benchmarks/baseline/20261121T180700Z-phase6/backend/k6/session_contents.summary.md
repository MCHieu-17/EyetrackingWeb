# k6 summary

scenario: session_contents

- http_req_duration: p(90)=21.194, p(95)=22.550, p(99)=24.538, avg=14.514, min=4.005, med=13.214, max=79.744
- http_req_waiting: avg=14.380, min=3.944, med=13.063, max=79.681, p(90)=21.074, p(95)=22.421, p(99)=24.403
- http_req_receiving: max=0.425, p(90)=0.201, p(95)=0.250, p(99)=0.349, avg=0.095, min=0.021, med=0.064
- http_req_duration{expected_response:true}: avg=14.514, min=4.005, med=13.214, max=79.744, p(90)=21.194, p(95)=22.550, p(99)=24.538
- http_req_connecting: p(99)=0.115, avg=0.003, min=0.000, med=0.000, max=0.193, p(90)=0.000, p(95)=0.000
- http_req_blocked: p(95)=0.015, p(99)=0.153, avg=0.014, min=0.001, med=0.011, max=0.223, p(90)=0.014
- http_req_sending: p(95)=0.056, p(99)=0.079, avg=0.039, min=0.005, med=0.040, max=0.114, p(90)=0.049
- http_req_failed: rate=0.000
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- iterations: count=233.000, rate=23.170
- vus: min=5.000, max=5.000
