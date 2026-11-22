# k6 summary

scenario: outline

- http_req_duration{expected_response:true}: avg=9.228, min=2.265, med=10.478, max=12.130, p(90)=11.620, p(95)=12.038, p(99)=12.112
- vus: max=1.000, min=1.000
- http_req_connecting: p(99)=0.065, avg=0.004, min=0.000, med=0.000, max=0.080, p(90)=0.000, p(95)=0.004
- http_req_receiving: med=0.139, max=0.233, p(90)=0.212, p(95)=0.222, p(99)=0.231, avg=0.128, min=0.034
- iterations: count=20.000, rate=4.756
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_failed: rate=0.000
- http_req_blocked: p(99)=0.100, avg=0.017, min=0.003, med=0.011, max=0.114, p(90)=0.016, p(95)=0.046
- http_req_duration: max=12.130, p(90)=11.620, p(95)=12.038, p(99)=12.112, avg=9.228, min=2.265, med=10.478
- http_req_sending: min=0.014, med=0.043, max=0.085, p(90)=0.049, p(95)=0.055, p(99)=0.079, avg=0.043
- http_req_waiting: avg=9.057, min=2.197, med=10.251, max=11.946, p(90)=11.451, p(95)=11.861, p(99)=11.929
