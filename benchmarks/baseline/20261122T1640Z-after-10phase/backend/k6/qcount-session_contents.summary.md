# k6 summary

scenario: session_contents

- vus: min=1.000, max=1.000
- http_req_connecting: p(99)=0.072, avg=0.004, min=0.000, med=0.000, max=0.089, p(90)=0.000, p(95)=0.004
- http_req_waiting: p(99)=15.089, avg=10.987, min=3.281, med=12.463, max=15.114, p(90)=14.816, p(95)=14.987
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_blocked: p(99)=0.100, avg=0.017, min=0.003, med=0.011, max=0.119, p(90)=0.016, p(95)=0.025
- http_req_receiving: min=0.030, med=0.129, max=0.221, p(90)=0.171, p(95)=0.188, p(99)=0.215, avg=0.121
- http_req_duration{expected_response:true}: med=12.626, max=15.302, p(90)=14.990, p(95)=15.214, p(99)=15.285, avg=11.152, min=3.323
- http_req_sending: avg=0.043, min=0.012, med=0.042, max=0.100, p(90)=0.052, p(95)=0.057, p(99)=0.091
- iterations: rate=4.712, count=20.000
- http_req_duration: min=3.323, med=12.626, max=15.302, p(90)=14.990, p(95)=15.214, p(99)=15.285, avg=11.152
- http_req_failed: rate=0.000
